pipeline "x" {
  param "n" {
    type = notatype
  }
  step "transform" "a" {
    value = param.n
  }
}
