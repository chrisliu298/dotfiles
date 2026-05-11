// Safe-copy CV skeleton. Compiles under Typst 0.14.2.

#set document(title: [Your Name — CV], author: ("Your Name",))
#set text(font: "Libertinus Serif", size: 10.5pt, lang: "en")
#set page("us-letter", margin: (x: 0.75in, y: 0.75in), numbering: none)
#set par(leading: 0.55em)
#show heading.where(level: 1): set text(size: 14pt, weight: "bold")
#show heading.where(level: 1): set block(above: 1em, below: 0.4em)
#show heading.where(level: 1): it => {
  it.body
  v(-0.2em)
  line(length: 100%, stroke: 0.6pt)
}

#align(center)[
  #text(size: 20pt, weight: "bold")[Your Name] \
  #v(0.2em)
  City · email\@example.com · #link("https://example.com")[example.com]
]
#v(0.5em)

= Experience

#grid(columns: (1fr, auto), gutter: 4pt,
  [*Role* — Company], [#h(1fr) 2024 — present],
)
- Bullet describing impact.
- Bullet describing impact.

#v(0.5em)

#grid(columns: (1fr, auto), gutter: 4pt,
  [*Previous Role* — Earlier Company], [#h(1fr) 2022 — 2024],
)
- Bullet describing impact.

= Education

#grid(columns: (1fr, auto), gutter: 4pt,
  [*B.S. in Major* — University], [#h(1fr) 2018 — 2022],
)
