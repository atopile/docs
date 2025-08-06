import numpy as np
from manim import (
    BLUE,
    DOWN,
    LEFT,
    ORANGE,
    PINK,
    PI,
    RIGHT,
    WHITE,
    TAU,
    UP,
    Arrow,
    ArrowTriangleFilledTip,
    ArrowTip,
    Brace,
    Circle,
    Create,
    Dot,
    FadeOut,
    Group,
    NumberLine,
    Rectangle,
    Scene,
    Square,
    Text,
    Transform,
    Line,
    VMobject,
    GREEN,
)
from manim.utils.space_ops import angle_of_vector


class SubsetIndicator(VMobject):
    def __init__(
        self,
        start,
        end,
        tip_length=0.25,
        tip_shape=ArrowTriangleFilledTip,
        color=WHITE,
        **kwargs,
    ):
        super().__init__(**kwargs)

        s = np.array(start)
        e = np.array(end)

        self.line = Line(s, e, color=color, **kwargs)

        line_vector = e - s
        if np.allclose(line_vector, np.zeros(3)):
            # Handle cases where start and end points are the same
            line_angle = 0.0
        else:
            line_angle = angle_of_vector(line_vector)

        # Tip at start, pointing outwards (away from end)
        self.tip_at_start = tip_shape(length=tip_length, color=color, **kwargs)
        # Rotate tip to align correctly: line_angle + PI (opposite to line dir)
        self.tip_at_start.rotate(line_angle + PI)
        self.tip_at_start.move_to(s)

        # Tip at end, pointing outwards (away from start)
        self.tip_at_end = tip_shape(length=tip_length, color=color, **kwargs)
        # Rotate tip to align correctly: line_angle (same as line dir)
        self.tip_at_end.rotate(line_angle)
        self.tip_at_end.move_to(e)

        self.add(self.line, self.tip_at_start, self.tip_at_end)


class SupersetIndicator(VMobject):
    def __init__(
        self,
        start,
        end,
        tip_length=0.25,
        tip_shape=ArrowTriangleFilledTip,
        color=WHITE,
        **kwargs,
    ):
        super().__init__(**kwargs)

        s = np.array(start)
        e = np.array(end)

        self.line = Line(s, e, color=color, **kwargs)

        line_vector = e - s
        if np.allclose(line_vector, np.zeros(3)):
            # Handle cases where start and end points are the same
            line_angle = 0.0
        else:
            line_angle = angle_of_vector(line_vector)

        # Tip at start, pointing inwards (towards end)
        self.tip_at_start = tip_shape(length=tip_length, color=color, **kwargs)
        # Rotate tip to align correctly: line_angle (same as line dir)
        self.tip_at_start.rotate(line_angle)
        self.tip_at_start.move_to(s)

        # Tip at end, pointing inwards (towards start)
        self.tip_at_end = tip_shape(length=tip_length, color=color, **kwargs)
        # Rotate tip to align correctly: line_angle + PI (opposite to line dir)
        self.tip_at_end.rotate(line_angle + PI)
        self.tip_at_end.move_to(e)

        self.add(self.line, self.tip_at_start, self.tip_at_end)


class Parameters(Scene):
    def construct(self):
        domain = NumberLine(
            x_range=[2.5, 4, 0.1],
            include_numbers=True,
            font_size=24,
            length=12,
        )
        self.play(Create(domain))
        multimeter_dot = Dot(domain.n2p(3.3), color=BLUE)
        self.play(Create(multimeter_dot))

        self.wait(1)
        self.next_section()
        self.play(FadeOut(multimeter_dot))

        power_supply_brace = Brace(
            Group(domain.get_tick(3.1), domain.get_tick(3.5)), UP
        )
        power_supply_brace_text = Text("Power Supply Voltage", font_size=24).next_to(
            power_supply_brace, UP
        )
        self.play(Create(power_supply_brace), Create(power_supply_brace_text))

        braces = [power_supply_brace, power_supply_brace_text]

        self.wait(1)
        self.next_section()

        microcontroller_brace = Brace(
            (Group(domain.get_tick(3.2), domain.get_tick(3.4)).shift(DOWN * 0.5)), DOWN
        )
        microcontroller_brace_text = Text(
            "Microcontroller Rated Voltage", font_size=24
        ).next_to(microcontroller_brace, DOWN)

        braces.append(microcontroller_brace)
        braces.append(microcontroller_brace_text)

        self.play(Create(microcontroller_brace), Create(microcontroller_brace_text))

        self.wait(1)
        self.next_section()

        multimeter_dot = Dot(domain.n2p(3.45), color=BLUE)
        multimeter_annotation = Text("Oops!", font_size=24).next_to(
            microcontroller_brace_text
        )
        multimeter_dot_arrow = Arrow(
            multimeter_annotation.get_edge_center(UP), multimeter_dot.get_center()
        )
        self.play(Create(multimeter_dot))
        self.play(Create(multimeter_dot_arrow), Create(multimeter_annotation))

        self.wait(1)
        self.next_section()

        self.play(
            FadeOut(multimeter_dot_arrow),
            FadeOut(multimeter_annotation),
            FadeOut(multimeter_dot),
        )

        # Add superset and subset constraints to the domain
        superset = SupersetIndicator(domain.n2p(3.1), domain.n2p(3.5), color=ORANGE)
        superset_title = Text("voltage ⊇ 3.1 to 3.5V", font_size=24, color=ORANGE)
        and_title = Text("&&", font_size=24).next_to(superset_title, RIGHT)
        subset = SubsetIndicator(domain.n2p(3.2), domain.n2p(3.4), color=GREEN)
        subset_title = Text("voltage ⊆ 3.2 to 3.4V", font_size=24, color=GREEN).next_to(
            and_title, RIGHT
        )

        title_group = (
            Group(superset_title, and_title, subset_title).center().shift(UP * 2)
        )

        self.play(Create(subset), Create(subset_title))
        self.wait(1)

        self.play(Create(superset), Create(superset_title), Create(and_title))
        self.wait(1)

        self.play(FadeOut(b) for b in braces)

        self.wait(1)

        new_subset = SubsetIndicator(domain.n2p(2.7), domain.n2p(3.7), color=GREEN)
        new_subset_title = Text(
            "voltage ⊆ 2.7 to 3.7V", font_size=24, color=GREEN
        ).next_to(and_title, RIGHT)

        self.play(
            Transform(subset, new_subset),
            Transform(subset_title, new_subset_title),
        )

        self.wait(1)
