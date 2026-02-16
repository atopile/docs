# Structure

* The target codebase to be documented is atopile/src/faebryk/library
* Python script will parse the library and directly generate markdown for mintlify within atopile/docs repo

# Example Page
---
title: "Resistor"
api: "COMP /components/Resistor"
icon: "microchip"
description: "A resistor is a two-terminal electrical component."
---

<RequestExample>
```ato Quick Example
module Example:
    r1 = new Resistor
    r1.resistance = 10kohm +/- 5%
    r1.max_power = 0.125W
    r1.max_voltage = 50V
```
</RequestExample>

## Parameters

The Resistor component has the following configurable parameters:

<ParamField path="resistance" type="ohm" required>
  Resistance of resistor in Ohms.
</ParamField>

<ParamField path="max_power" type="W" required>
  Maximum power dissipation rating in Watts.
</ParamField>

<ParamField path="max_voltage" type="V" required>
  Maximum voltage rating in Volts.
</ParamField>


## Interfaces

Connection points for the resistor:

<ParamField path="unnamed" type="Electrical[2]">
  Array of 2 Electrical connection points
</ParamField>


## Properties

Convenience properties for accessing resistor terminals:

<ParamField path="p1" type="Electrical" readonly>
  One side of the resistor.
</ParamField>

<ParamField path="p2" type="Electrical" readonly>
  The other side of the resistor.
</ParamField>


## Traits

The Resistor component automatically includes these traits:

### [pickable](/atopile/api-reference/traits/pickable)
Enables automatic part selection from the component database based on resistance, power, and voltage requirements.

### [can_bridge](/atopile/api-reference/traits/can-bridge)
Allows the resistor to be used in bridging connections with the `~>` operator for series connections.

### [simple_value_representation](/atopile/api-reference/traits/simple-value-representation)
Provides a simplified string representation showing key parameters for debugging and documentation.

## Package Selection

The resistor's package is automatically selected based on the power rating:
- **0402, 0603**: Up to 0.1W (1/10 watt)
- **0805**: Up to 0.125W (1/8 watt) 
- **1206**: Up to 0.25W (1/4 watt)
- **1210, 2010**: Higher power ratings

## Best Practices

1. **Always use tolerances**: Real resistors have tolerances. Use `+/- 5%` for standard parts, `+/- 1%` for precision.

2. **Power derating**: Choose power rating 2x higher than calculated dissipation for safety margin.

3. **Standard values**: Use E12 series values (1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2) for better availability.

4. **Voltage rating**: Ensure max_voltage exceeds your circuit's maximum voltage.
