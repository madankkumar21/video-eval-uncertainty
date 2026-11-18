from manim import *
from explainer_base import ExplainerScene, T

# Every number here comes from docs/video-brief.md in video-eval-uncertainty (commit 041c36c).
HAIKU_C = BLUE_C
SONNET_C = TEAL_B
OPUS_C = PURPLE_B
ERR_C = RED_C
DIM = GREY_B


def bar(x, pct, color, width=1.2, base_y=-1.6, scale=0.04):
    r = Rectangle(width=width, height=pct * scale, fill_color=color, fill_opacity=0.85, stroke_width=0)
    r.move_to([x, base_y, 0], aligned_edge=DOWN)
    return r


def err(x, lo, hi, base_y=-1.6, scale=0.04):
    y0, y1 = base_y + lo * scale, base_y + hi * scale
    g = VGroup(Line([x, y0, 0], [x, y1, 0], color=ERR_C, stroke_width=5),
               Line([x - 0.25, y0, 0], [x + 0.25, y0, 0], color=ERR_C, stroke_width=5),
               Line([x - 0.25, y1, 0], [x + 0.25, y1, 0], color=ERR_C, stroke_width=5))
    return g


class Explainer(ExplainerScene):
    def construct(self):
        title = T("What one accuracy number hides", 40).to_edge(UP, buff=0.35)

        # ---------- Scene 1: the question ----------
        b_a = bar(-1.5, 85, GREY_A); b_b = bar(1.5, 84, GREY_A)
        l_a = T("model A  85%", 30).next_to(b_a, UP, buff=0.15)
        l_b = T("model B  84%", 30).next_to(b_b, UP, buff=0.15)
        base = Line([-4, -1.6, 0], [4, -1.6, 0], color=DIM)
        self.beat(0, Write(title), Create(base), GrowFromEdge(b_a, DOWN), GrowFromEdge(b_b, DOWN),
                  FadeIn(l_a), FadeIn(l_b), rt=1.6)
        q = T("A difference, or noise?", 44, YELLOW).move_to(DOWN * 2.6)
        self.beat(1, FadeIn(q, scale=0.9))

        # ---------- Scene 2: the headline ----------
        scope = T("100 items · one task: MVBench action_count · 3 models, same items", 20, DIM).to_corner(DR, buff=0.25)
        setup = VGroup(T("MVBench action_count", 34),
                       T('"How many times did the person do X?"', 30, GREY_A),
                       T("first 100 of 200 items · 8 frames per video", 26, DIM)).arrange(DOWN, buff=0.25)
        self.beat(2, FadeOut(VGroup(b_a, b_b, l_a, l_b, q, base)), FadeIn(setup), FadeIn(scope), rt=1.2)
        chance = T("3 options  →  guessing = 33.3%", 30, YELLOW).next_to(setup, DOWN, buff=0.5)
        self.beat(3, FadeIn(chance, shift=UP * 0.2))

        xs = [-1.3, 1.9, 5.1]
        names = ["Opus 5.5", "Sonnet 5.5", "Haiku 4.5"]
        subs = ["medium effort", "thinking off", "temperature 0"]
        accs = [52, 48, 44]
        cis = [(42.3, 61.5), (38.5, 57.7), (34.7, 53.8)]
        cols = [OPUS_C, SONNET_C, HAIKU_C]
        axis = Line([-5.4, -1.6, 0], [6.3, -1.6, 0], color=DIM)
        bars = VGroup(*[bar(x, a, c) for x, a, c in zip(xs, accs, cols)])
        acc_lbls = VGroup(*[T(f"{a}%", 34).next_to(b, UP, buff=0.12) for a, b in zip(accs, bars)])
        name_lbls = VGroup(*[VGroup(T(n, 26), T(s, 20, DIM)).arrange(DOWN, buff=0.06).next_to(b, DOWN, buff=0.15)
                             for n, s, b in zip(names, subs, bars)])
        chance_y = -1.6 + 33.3 * 0.04
        chance_line = DashedLine([-5.4, chance_y, 0], [6.3, chance_y, 0], color=YELLOW)
        chance_lbl = T("guessing 33.3%", 20, YELLOW).move_to([-4.0, chance_y - 0.3, 0])
        self.beat(4, Succession(FadeOut(VGroup(setup, chance)),
                                AnimationGroup(Create(axis), Create(chance_line), FadeIn(chance_lbl),
                                               *[GrowFromEdge(b, DOWN) for b in bars], FadeIn(acc_lbls), FadeIn(name_lbls))),
                  rt=2.0)

        errs = VGroup(*[err(x, lo, hi) for x, (lo, hi) in zip(xs, cis)])
        ci_lbls = VGroup(*[T(f"[{lo}%, {hi}%]", 18, WHITE).move_to([x, -1.3, 0]) for x, (lo, hi) in zip(xs, cis)])
        wil = T("95% Wilson intervals", 22, ERR_C).to_edge(RIGHT, buff=0.4).shift(UP * 2.0)
        self.beat(5, *[Create(e) for e in errs], FadeIn(ci_lbls), FadeIn(wil), rt=1.2)

        tied = VGroup(T("Opus vs Sonnet   p = 0.56   tied", 24),
                      T("Sonnet vs Haiku  p = 0.64   tied", 24),
                      T("Opus vs Haiku    p = 0.28   tied", 24)).arrange(DOWN, aligned_edge=LEFT, buff=0.12)
        tied.to_edge(LEFT, buff=0.3).shift(UP * 1.2)
        not_rank = T("not a ranking", 26, YELLOW).next_to(tied, DOWN, buff=0.25).align_to(tied, LEFT)
        self.beat(6, FadeIn(tied, shift=RIGHT * 0.2), FadeIn(not_rank), rt=1.2)

        tied_def = T("tied = not distinguishable on this data, not identical", 22, GREY_A)
        tied_def.next_to(title, DOWN, buff=0.2)
        self.beat(7, FadeIn(tied_def))
        bonf = T("10 paired tests · none survives Bonferroni (alpha 0.005)", 22, GREY_A).next_to(tied_def, DOWN, buff=0.15)
        self.beat(8, FadeIn(bonf))

        # ---------- Scene 3: items needed ----------
        chart = VGroup(axis, bars, acc_lbls, name_lbls, chance_line, chance_lbl, errs, ci_lbls, wil, tied, not_rank, tied_def, bonf)
        est = T("ESTIMATES  (80% power, alpha 0.05, observed disagreement)", 22, YELLOW).next_to(title, DOWN, buff=0.25)
        rows = [("8-point gap  (Opus vs Haiku)", "about 510"),
                ("4-point gap  (Opus vs Sonnet)", "about 1,270"),
                ("4-point gap  (Sonnet vs Haiku)", "about 2,060")]
        LX, RX = -5.2, 2.2
        ys = [1.5, 0.8, 0.1, -0.6]
        hdr = VGroup(T("gap to detect", 26, DIM).move_to([LX, ys[0], 0], aligned_edge=LEFT),
                     T("items needed", 26, DIM).move_to([RX, ys[0], 0], aligned_edge=LEFT))
        table = VGroup(hdr, *[VGroup(T(g, 28).move_to([LX, y, 0], aligned_edge=LEFT),
                                     T(n, 28, YELLOW).move_to([RX, y, 0], aligned_edge=LEFT)) for (g, n), y in zip(rows, ys[1:])])
        self.beat(9, FadeOut(chart), FadeIn(est), FadeIn(hdr), rt=1.0)
        self.beat(10, LaggedStart(*[FadeIn(r, shift=RIGHT * 0.2) for r in table[1:]], lag_ratio=0.3), rt=1.6)
        have = T("the whole task has 200 items", 34, ERR_C).move_to(DOWN * 2.0)
        self.beat(11, FadeIn(have, scale=0.9))

        # ---------- Scene 4: Haiku guesses the middle ----------
        s3 = VGroup(est, table, have)
        sub4 = T("What the number hides: Haiku 4.5", 30, HAIKU_C).next_to(title, DOWN, buff=0.25)
        cols_x = [-2.6, 0.0, 2.6]
        letters = VGroup(*[T(L, 40).move_to([x, 1.7, 0]) for L, x in zip("ABC", cols_x)])
        truth_mid = VGroup(T("right answer here on", 22, DIM), T("35 / 100", 36)).arrange(DOWN, buff=0.08).move_to([0, 0.7, 0])
        self.beat(12, FadeOut(s3), FadeIn(sub4), FadeIn(letters), FadeIn(truth_mid), rt=1.2)
        pick_mid = VGroup(T("Haiku picks it", 22, HAIKU_C), T("59 / 100", 44, HAIKU_C)).arrange(DOWN, buff=0.08).move_to([0, -0.8, 0])
        self.beat(13, FadeIn(pick_mid, scale=0.8), Indicate(letters[1], color=HAIKU_C), rt=1.2)
        acc_pos = VGroup(*[T(f"{v}%", 32, c).move_to([x, -2.2, 0])
                           for v, x, c in zip([23, 74, 33], cols_x, [DIM, HAIKU_C, DIM])])
        acc_cap = T("Haiku accuracy when the right answer sits at A / B / C", 22, GREY_A).move_to(DOWN * 2.8)
        self.beat(14, LaggedStart(*[FadeIn(a, shift=UP * 0.2) for a in acc_pos], lag_ratio=0.3), FadeIn(acc_cap), rt=1.4)
        temp = T("default temperature: still 55 / 100 on the middle", 24, GREY_A).next_to(pick_mid, RIGHT, buff=0.6)
        self.beat(15, FadeIn(temp, shift=LEFT * 0.2))

        # ---------- Scene 5: the shuffle test ----------
        s4 = VGroup(sub4, letters, truth_mid, pick_mid, acc_pos, acc_cap, temp)
        sub5 = T("The shuffle test", 30, YELLOW).next_to(title, DOWN, buff=0.25)
        self.beat(16, FadeOut(s4), FadeIn(sub5), rt=1.0)

        def options(vals, y):
            return VGroup(*[T(f"({L})  {v}", 36).move_to([x, y, 0]) for L, v, x in zip("ABC", vals, cols_x)])

        opts = options(["3", "2", "4"], 0.9)
        pick_box = SurroundingRectangle(opts[1], color=HAIKU_C, buff=0.15)
        pick_lbl = T("Haiku's pick", 22, HAIKU_C).next_to(pick_box, UP, buff=0.12)
        illus = T("one item, illustrative values", 20, DIM).move_to([0, 2.0, 0])
        self.beat(17, FadeIn(opts), Create(pick_box), FadeIn(pick_lbl), FadeIn(illus), rt=1.0)
        # animate: content moves, pick stays on B
        opts2 = options(["2", "4", "3"], 0.9)
        self.play(Transform(opts, opts2), run_time=1.0)
        stays = T("content moved · pick stays on B", 26, YELLOW).move_to([0, -0.3, 0])
        self.play(FadeIn(stays), run_time=0.5)

        split = VGroup(
            VGroup(T("followed the answer", 22, GREY_A), T("28", 44)).arrange(DOWN, buff=0.1),
            VGroup(T("stayed on the letter", 22, GREY_A), T("28", 44, HAIKU_C)).arrange(DOWN, buff=0.1),
            VGroup(T("third option", 22, GREY_A), T("6", 44)).arrange(DOWN, buff=0.1),
        ).arrange(RIGHT, buff=1.2).move_to(DOWN * 2.1)
        split_cap = T("Haiku, 62 items where its chosen option moved", 22, DIM).next_to(split, DOWN, buff=0.25)
        self.beat(18, FadeIn(split, shift=UP * 0.2), FadeIn(split_cap), rt=1.4)

        # ---------- Scene 6: the contrast ----------
        s5 = VGroup(sub5, opts, pick_box, pick_lbl, illus, stays, split, split_cap)
        sub6 = T("The contrast", 30, YELLOW).next_to(title, DOWN, buff=0.25)
        son = VGroup(T("Sonnet 5.5", 32, SONNET_C),
                     T("followed the answer on 56 of 64 moved items", 26),
                     T("two runs agreed on 93 of 100 answers", 26, GREY_A)).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        son.move_to(UP * 1.1).to_edge(LEFT, buff=0.8)
        self.beat(19, FadeOut(s5), FadeIn(sub6), FadeIn(son, shift=RIGHT * 0.2), rt=1.2)
        opu = VGroup(T("Opus 5.5", 32, OPUS_C),
                     T("followed the answer on 40 of 64 moved items", 26),
                     T("no position preference: 13 same letter vs 11 third option, p = 0.42", 24, GREY_A)
                     ).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
        opu.next_to(son, DOWN, buff=0.6).align_to(son, LEFT)
        self.beat(20, FadeIn(opu, shift=RIGHT * 0.2), rt=1.2)
        contrast = T("Similar scores. Very different behavior.", 36, YELLOW).move_to(DOWN * 2.6)
        self.beat(21, FadeIn(contrast, scale=0.9))

        # ---------- Scene 7: a fragile result ----------
        s6 = VGroup(sub6, son, opu, contrast)
        sub7 = T("A fragile result", 30, YELLOW).next_to(title, DOWN, buff=0.25)
        lab = VGroup(T("Haiku, options labelled A / B / C", 28), T("44%", 44, HAIKU_C)).arrange(DOWN, buff=0.1).move_to(LEFT * 3.0 + UP * 0.8)
        lab2 = VGroup(T("Haiku, options labelled 1 / 2 / 3", 28), T("35%", 44, ERR_C)).arrange(DOWN, buff=0.1).move_to(RIGHT * 3.0 + UP * 0.8)
        arrow = Arrow(lab.get_right(), lab2.get_left(), buff=0.3, color=DIM)
        p1 = T("p = 0.022", 30).move_to(DOWN * 0.6)
        self.beat(22, FadeOut(s6), FadeIn(sub7), FadeIn(lab), GrowArrow(arrow), FadeIn(lab2), FadeIn(p1), rt=1.4)
        p2 = T("one item flips  →  p = 0.092, a tie", 30, ERR_C).next_to(p1, DOWN, buff=0.25)
        self.beat(23, FadeIn(p2, shift=UP * 0.2))
        real = VGroup(T("still real: Haiku repeated all 100 answers exactly, so this is not sampling noise", 24, GREY_A),
                      T("too small for 100 items to pin down", 24, GREY_A)).arrange(DOWN, buff=0.15).move_to(DOWN * 2.4)
        self.beat(24, FadeIn(real))

        # ---------- Scene 8: so what ----------
        s7 = VGroup(sub7, lab, lab2, arrow, p1, p2, real)
        sub8 = T('Before trusting "A beats B by N points", ask:', 32).next_to(title, DOWN, buff=0.4)
        self.beat(25, FadeOut(s7), FadeIn(sub8), rt=1.0)
        qs = VGroup(T("1.  What are the intervals?", 34),
                    T("2.  How many items would a gap that size need?", 34),
                    T("3.  Does the score survive shuffling the options?", 34)).arrange(DOWN, aligned_edge=LEFT, buff=0.45)
        qs.move_to(UP * 0.2)
        for k in range(3):
            self.beat(26 + k, FadeIn(qs[k], shift=RIGHT * 0.3))
        final = T("This repo answers all three, for any model, on any MVBench slice.", 28, YELLOW)
        final.add_background_rectangle(color=BLACK, opacity=0.85, buff=0.2).move_to(DOWN * 2.6)
        self.beat(29, FadeIn(final, scale=0.9))
        self.wait(0.8)
