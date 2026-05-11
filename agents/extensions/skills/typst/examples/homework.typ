// Safe-copy homework skeleton. Compiles under Typst 0.14.2.

#set document(title: [Homework N], author: ("Your Name",))
#set text(font: "Libertinus Serif", size: 11pt, lang: "en")
#set page("us-letter", margin: 1in, header: align(right)[Your Name · Course])
#set par(leading: 0.7em)
#set enum(numbering: "1.")
#set math.equation(numbering: "(1)")

#align(center)[
  #text(size: 14pt, weight: "bold")[Course · Homework N] \
  Your Name · #datetime.today().display("[year]-[month]-[day]")
]
#v(1em)

#let problem(n, body) = [
  *Problem #n.* #body
]

#problem(1)[
  Statement of the first problem.

  *Solution.* Working below.
  $ x = (-b plus.minus sqrt(b^2 - 4 a c)) / (2 a) $
]

#problem(2)[
  Statement of the second problem.

  *Solution.* Working below.
]
