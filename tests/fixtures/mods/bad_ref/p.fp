pipeline "x" {
  step "transform" "a" {
    value = step.transform.nope.value
  }
}
