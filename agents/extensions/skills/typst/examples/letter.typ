// Safe-copy letter skeleton. Compiles under Typst 0.14.2.

#set document(title: [Letter], author: ("Your Name",))
#set text(font: "Libertinus Serif", size: 11pt, lang: "en")
#set page("us-letter", margin: (x: 1in, y: 1in))
#set par(justify: true, leading: 0.65em)

#align(right)[
  Your Name \
  Street Address \
  City, ST ZIP
]

#v(1em)

#datetime.today().display("[month repr:long] [day], [year]")

#v(1em)

Recipient Name \
Recipient Title \
Organization \
Address

#v(1em)

Dear Recipient Name,

Body of the letter. Replace this paragraph with the actual message.

Closing paragraph stating the requested next step.

#v(1em)

Sincerely,

#v(2em)
Your Name
