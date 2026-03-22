# Math Mode Reference

## Inline vs display

```typst
$x^2 + y^2$           // inline — no spaces inside $
$ x^2 + y^2 $         // display (block) — spaces inside $
```

The only difference is the presence of spaces/newlines after `$` and before `$`.

## Subscripts and superscripts

```typst
$ x^2 $               // superscript
$ x_i $               // subscript
$ x_i^2 $             // both
$ x_(i+1)^(n-1) $     // multi-character: use parentheses
$ sum_(i=0)^n $        // on operators
```

## Fractions

Typst auto-creates fractions from `/` with correct precedence:

```typst
$ (a + b) / c $        // fraction
$ a/b $                // simple fraction
$ 1 / (x^2 + 1) $     // parentheses control grouping
$ frac(a, b) $         // explicit frac() function also works
```

## Alignment and line breaks

Use `\` for line breaks and `&` for alignment points:

```typst
$ x &= 2 + 3 \
    &= 5 $
```

Multiple alignment points create alternating right/left columns:

```typst
$ (3x + y) / 7 &= 9 && "given" \
  3x + y &= 63 & "multiply by 7" \
  3x &= 63 - y && "subtract y" \
  x &= 21 - y/3 & "divide by 3" $
```

## Symbols

Greek letters and math symbols by name:

```typst
$ alpha, beta, gamma, delta, epsilon, pi, sigma, omega $
$ Gamma, Delta, Theta, Lambda, Pi, Sigma, Omega $      // capital
$ infinity, partial, nabla, forall, exists $
```

### Shorthands

```typst
$ -> $     // →   rightarrow
$ <- $     // ←   leftarrow
$ <-> $    // ↔   left-right arrow
$ => $     // ⇒   double arrow
$ |-> $    // ↦   maps to
$ >= $     // ≥
$ <= $     // ≤
$ != $     // ≠
$ ~ $      // ~ (tilde operator)
$ ... $    // …   ellipsis
$ :: $     // ∷
```

### Symbol modifiers

Append modifiers with dots to change symbol variants:

```typst
$ arrow.r $           // →
$ arrow.l $           // ←
$ arrow.r.long $      // ⟶
$ arrow.l.squiggly $  // ↜
$ tilde.eq $          // ≃
```

## Text in math

Single letters are variables. Multi-letter names are interpreted as symbol/function names. Use quotes for literal text:

```typst
$ x "if" x > 0 $
$ "area" = pi r^2 $
$ f(x) = cases(
  1 "if" x > 0,
  0 "otherwise",
) $
```

## Common math functions

### cases

```typst
$ f(x) = cases(
  x^2 &"if" x >= 0,
  -x  &"if" x < 0,
) $
```

### vec (vectors)

```typst
$ vec(1, 2, 3) $
$ vec(x_1, x_2, dots.v, x_n) $
$ vec(delim: "[", 1, 2) $    // square brackets
```

### mat (matrices)

Rows separated by `;`, columns by `,`:

```typst
$ mat(
  1, 2, 3;
  4, 5, 6;
  7, 8, 9;
) $

$ mat(delim: "[",
  a, b;
  c, d;
) $

// Augmented matrix
$ mat(augment: #2,
  1, 0, 0;
  0, 1, 1;
) $
```

### binom (binomial coefficients)

```typst
$ binom(n, k) = n! / (k!(n-k)!) $
```

### lr (manual delimiter sizing)

Typst auto-scales delimiters. To override:

```typst
$ lr([ sum_(i=0)^n i ]) $          // force specific delimiters
```

To prevent auto-scaling, use backslash-escaped delimiters:

```typst
$ \( x + y \) $                    // unscaled parentheses
```

### Delimiter helpers

Built-in shorthand functions for common delimiters:

```typst
$ abs(x) $            // |x|
$ norm(x) $           // ‖x‖
$ floor(x) $          // ⌊x⌋
$ ceil(x) $           // ⌈x⌉
$ round(x) $          // (x) with auto-scaled parentheses (not numeric rounding)
$ lr({ x mid(|) x > 0 }) $  // set-builder notation with scaled |
```

### underbrace / overbrace

```typst
$ underbrace(1 + 2 + dots.c + n, n "terms") $
$ overbrace(a + b + c, "total") $
```

Also: `underbracket`, `overbracket`, `underparen`, `overparen`.

### cancel (strikethrough)

```typst
$ (a dot b dot cancel(x)) / cancel(x) $
$ cancel(Pi, cross: #true) $
$ cancel(sum x, stroke: #(paint: red, thickness: 1.5pt, dash: "dashed")) $
```

### accent

```typst
$ accent(x, hat) $     // x̂  — or use shorthand: $hat(x)$
$ accent(x, tilde) $   // x̃
$ accent(x, dot) $     // ẋ
$ accent(x, macron) $  // x̄  — or $overline(x)$
```

Common accent shorthands: `hat(x)`, `tilde(x)`, `dot(x)`, `dot.double(x)`, `macron(x)`, `vec(x)` (arrow accent).

### op (custom operators)

```typst
$ op("argmax", limits: #true)_(theta) L(theta) $
```

`limits: true` places sub/superscripts above/below (like `\limits` in LaTeX).

Predefined operators (no `op()` needed): `sin`, `cos`, `tan`, `cot`, `sec`, `csc`, `sinh`, `cosh`, `tanh`, `arcsin`, `arccos`, `arctan`, `log`, `lg`, `ln`, `exp`, `lim`, `liminf`, `limsup`, `max`, `min`, `sup`, `inf`, `det`, `dim`, `ker`, `hom`, `gcd`, `lcm`, `mod`, `deg`, `arg`, `Pr`, `tr`.

### Math variants (typefaces)

```typst
$ bb(R) $             // ℝ — blackboard bold (also: NN, ZZ, QQ, RR, CC)
$ cal(L) $            // calligraphic
$ scr(H) $            // script/roundhand
$ frak(g) $           // Fraktur
$ mono(x + y) $       // monospace
$ sans(A) $           // sans-serif
$ bold(x) $           // bold
$ italic(A) $         // italic
$ upright(d) $        // upright (e.g., for differential d)
```

### Limits vs scripts positioning

```typst
$ limits(sum)_(i=0)^n $    // force above/below (display style)
$ scripts(sum)_(i=0)^n $   // force beside (inline style)
```

### stretch (extensible symbols)

```typst
$ H stretch(=)^"define" U + p V $
$ f : X stretch(->>, size: #150%)_"surjective" Y $
```

### Size control

```typst
$ sum_i x_i/2 = display(sum_i x_i/2) $    // force display size
$ inline(sum_i x_i) $                       // force inline size
```

## Equation numbering

```typst
#set math.equation(numbering: "(1)")

$ E = m c^2 $ <eq:einstein>

As shown in @eq:einstein, ...
```

## Math fonts

```typst
#show math.equation: set text(font: "Fira Math")
```

Only OpenType math fonts work for math mode. Common choices: New Computer Modern Math, STIX Two Math, Fira Math, Libertinus Math.

## Spacing in math

Typst handles spacing automatically in most cases. For manual control:

```typst
$ a thin b $          // thin space
$ a med b $           // medium space
$ a thick b $         // thick space
$ a quad b $          // quad space
$ a #h(1em) b $       // arbitrary space (need # for code in math)
```

## Code expressions in math

Use `#` to drop into code mode within math:

```typst
$ (a + b)^2 = a^2 + text(fill: #maroon, 2 a b) + b^2 $
$ sum_(i=1)^#x i $     // use variable from code
```

## Accessibility

```typst
#math.equation(
  block: true,
  alt: "The integral of f of x dx from a to b",
  $ integral_a^b f(x) dif x $,
)
```
