import pytest

from opslens.sql import guard

pytestmark = pytest.mark.unit

OK = [
    "select 1",
    "SELECT volume_id FROM aws_ebs_volume WHERE state = 'available';",
    "with a as (select * from aws_ebs_volume) select count(*) from a",
    "select * from aws_ebs_volume union all select * from aws_ebs_volume",
    "select cidr from aws_vpc_subnet where cidr_block <<= '10.0.0.0/8'::cidr",
]
BAD = [
    ("drop table aws_ebs_volume", "only SELECT"),
    ("delete from aws_ebs_volume", "only SELECT"),
    ("select 1; select 2", "exactly one statement"),
    ("select 1; drop table x", "exactly one statement"),
    ("select pg_sleep(100)", "pg_sleep"),
    ("select pg_read_file('/etc/passwd')", "pg_read_file"),
    ("select * into newt from aws_ebs_volume", "not allowed"),
    ("copy aws_ebs_volume to '/tmp/x'", ""),
    ("set role admin", ""),
    ("", "empty"),
    ("select from where", ""),
]


@pytest.mark.parametrize("sql", OK)
def test_allows_read_only(sql):
    assert guard.check_select(sql)


@pytest.mark.parametrize("sql,why", BAD)
def test_refuses_everything_else(sql, why):
    with pytest.raises(guard.UnsafeSQL) as e:
        guard.check_select(sql)
    assert why in str(e.value)


def test_tables_in_ignores_ctes_and_schema_qualifiers():
    sql = "with v as (select * from aws_ebs_volume) select * from v join public.aws_vpc_eip e on true"
    assert guard.tables_in(sql) == {"aws_ebs_volume", "aws_vpc_eip"}


def test_allow_list():
    allowed = {"aws_ebs_volume"}
    assert guard.check_tables("select * from aws_ebs_volume", allowed)
    with pytest.raises(guard.UnsafeSQL, match="aws_iam_user"):
        guard.check_tables("select * from aws_iam_user", allowed)


@pytest.mark.parametrize("sql", ["select * from information_schema.tables", "select * from pg_catalog.pg_user",
                                 "select * from steampipe_internal.steampipe_connection"])
def test_system_schemas_are_never_readable(sql):
    with pytest.raises(guard.UnsafeSQL, match="not allowed"):
        guard.check_tables(sql, {"tables", "pg_user", "steampipe_connection"})
