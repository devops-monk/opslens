pipeline "approve" {
  step "input" "ok" {
    type     = "button"
    prompt   = "Delete?"
    notifier = notifier.default
    option "yes" { label = "Approve" }
    option "no" { label = "Skip" }
  }
  step "transform" "after" {
    if    = step.input.ok.value == "yes"
    value = "deleted"
  }
  output "done" { value = "ok" }
}
