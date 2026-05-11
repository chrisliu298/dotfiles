// Smoke test for the typst skill's load-bearing examples.
// Exercises every snippet that an earlier version of the skill emitted broken.
// Should compile cleanly under Typst 0.14.2.

#set document(title: [Smoke Test], author: ("typst-skill",))
#set text(lang: "en")
#set page(numbering: "1")
#set heading(numbering: "1.1")
#set math.equation(numbering: "(1)")

= Intro <intro>
See @intro.

// counter().display() needs #context at top level
#context counter(figure.where(kind: table)).display()

// heading show-rule guards numbering
#show heading.where(level: 1): it => {
  set text(navy, size: 16pt)
  block(below: 1em)[
    #if it.numbering != none [
      #counter(heading).display(it.numbering)~
    ]
    #smallcaps(it.body)
  ]
}

= Heading after show-rule

// list marker [\*] not [*]
#set list(marker: ([--], [\*]))
- top level
  - nested

// math uses partial / dif, not diff
$ partial f / partial x $
$ integral_a^b f(x) dif x $

// vec(x) is column vector, arrow(x) is the accent
$ vec(1, 2, 3) $
$ arrow(x) $

// sect deprecated → inter
$ A inter B $

// theorem via figure(kind:) — referenceable
#let theorem(body, title: none) = figure(
  kind: "theorem",
  supplement: [Theorem],
  numbering: "1",
  caption: none,
  block(
    width: 100%, inset: 10pt,
    stroke: (left: 2pt + navy),
    fill: navy.lighten(95%),
  )[
    #if title != none [*#title.* ]
    #body
  ],
)

#show figure.where(kind: "theorem"): it => block[
  *#it.supplement #context it.counter.display(it.numbering).* #it.body
]

#theorem[$a^2 + b^2 = c^2$] <thm:pyth>
See @thm:pyth.

// Labels attach to anything; #link / #ref work for arbitrary labels
#block[Important note] <note>
#link(<note>)[see note]
#ref(<note>, form: "page")

// Loop array shape
#let doubled = for n in (1, 2, 3) { (2 * n,) }
Doubled: #doubled

// Responsive layout — body is bound
#let responsive-columns(body) = layout(size => {
  if size.width > 400pt { columns(2, body) } else { body }
})
#responsive-columns[#lorem(40)]
