# Script

## Uncertainty

Let's check out a real-life parameter in your circuit - the voltage on your power rail.
You whip out your trusty cheap-o multimeter and check the voltage between vcc and gnd.

You see 3.3V {enter number line - mark 3.3V on the number line}

Perfect! Right?

Well... sometimes, but, often, not really. {fade out multimeter dot}

You know that right now, under these conditions, this specific power supply is putting out something around 3.3V, down to the precision of your power supply and multimeter.

For all of these reasons, we typically think of a measurement as having some **uncertainty** or range of possible values {number line add brace}
This represents the set of possible values this power supply will output, under rated conditions.

## Perspectives

Now, only the deepest of electronics nerds build a power supply for power-supply's sake! Let's plug it into this microcontroller. Annd... bang! There goes the blue smoke.

What happened? Well, doing my homework, it turns out that this microcontroller is only rated for this {add another brace} subset of voltages, and my multimeter is now saying the power supply is putting out {add dot} too much for it.

We need a good way to express two constraints of this voltage:
- The microcontroller needs the voltage to be within a range to operate correctly
- The power supply will, under rated conditions, output a voltage within this range, but we can't say exactly where

Looking at these as separate constraints, implies there is *something* that is constrained. In `atopile`, we refer to specific attributes of the design, like this voltage, as a `Parameter`.

With that, we can say:
- From the microcontroller: the voltage must be a **subset** of 3.2 to 3.3V
- From the power supply: the voltage is a **superset** of 3.1 to 3.5V

{fade out braces}

Now, this cannot be satisfied! There is a contradiction here. Which is exactly why the compiler will throw a contradiction error.

Instead, if buy a microcontroller with much more sane tolerances {widen microcontroller subset}, thing will work just fine.

## Correlation

Conveniently, this constraint-based thinking propagates super clearly too!
