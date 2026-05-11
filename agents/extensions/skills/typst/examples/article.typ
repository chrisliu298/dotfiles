// Safe-copy article skeleton. Compiles under Typst 0.14.2.

#set document(title: [Title], author: ("Author Name",))
#set text(font: "Libertinus Serif", size: 11pt, lang: "en")
#set par(justify: true, leading: 0.65em)
#set page("us-letter", margin: (x: 1in, y: 1in), numbering: "1")
#set heading(numbering: "1.1")
#set math.equation(numbering: "(1)")

#align(center)[
  #text(size: 18pt, weight: "bold")[Title] \
  #v(0.4em)
  Author Name · #datetime.today().display("[month repr:long] [day], [year]")
]
#v(1em)

#align(center)[
  #block(width: 80%)[
    *Abstract.* One-paragraph summary of the work.
  ]
]
#v(1em)

= Introduction
Body text.

= Methods
$ E = m c^2 $ <eq:einstein>

See @eq:einstein.

= Results
#figure(
  rect(width: 60%, height: 3cm, fill: luma(230))[plot placeholder],
  caption: [Caption goes here.],
) <fig:plot>

As shown in @fig:plot.

= Conclusion
Body text.
