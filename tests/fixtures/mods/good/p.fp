pipeline "hello" {
  param "name" {
    type    = string
    default = "world"
  }
  step "transform" "greet" {
    value = "hello ${param.name}"
  }
  output "msg" {
    value = step.transform.greet.value
  }
}
