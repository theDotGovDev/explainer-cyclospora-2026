#!/usr/bin/env python3
"""Generate data/top100.json - the 100 most commonly eaten U.S. foods, risk-rated.

Run from the repo root:  python3 tools/gen_top100.py

Two things this file is deliberately explicit about:

1. The ORDERING is an editorial approximation of how commonly each food is eaten
   in the United States, informed by USDA per-capita availability categories. It
   is not a published ranking, and no agency publishes one in this form. It is
   here to answer "is the thing I eat every day on this list", not to assert that
   item 34 outranks item 35.

2. The RISK TIERS carry the actual reasoning. Cyclospora cayetanensis is spread
   by fresh produce and water contaminated with sporulated oocysts. It is not a
   meat, dairy, egg, grain or shelf-stable food pathogen, and cooking destroys
   it. So most of this list is negligible-risk for a reason that is worth stating
   plainly rather than burying: the parasite simply does not occur there.

Assigning risk by tier rather than per food keeps 100 entries internally
consistent - two foods handled the same way cannot end up with different numbers.
"""

import collections
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# tier -> (low, high, basis).  low/high are the "1 in N" denominators.
TIERS = collections.OrderedDict([
    ("raw-herb", (50_000, 500_000,
     "Raw leafy herbs. Crinkled leaf surfaces are close to a worst case for "
     "rinsing off oocysts, and herbs have a real U.S. outbreak history.")),
    ("raw-leafy", (200_000, 2_000_000,
     "Raw leafy greens not implicated in 2026. Large folded surface area, eaten "
     "uncooked, and leafy greens have appeared in past outbreaks.")),
    ("raw-soft", (500_000, 5_000_000,
     "Raw produce eaten whole and unpeeled, where the surface cannot be scrubbed "
     "hard. Washing helps only partially.")),
    ("raw-firm", (1_000_000, 10_000_000,
     "Raw produce with a smooth firm surface that can be rinsed and rubbed, or "
     "an outer layer that is discarded.")),
    ("peeled", (2_000_000, 10_000_000,
     "Peeled before eating. Contamination is a surface phenomenon, so removing "
     "the skin removes essentially all of it. Residual risk is knife "
     "cross-contamination from rind to flesh.")),
    ("cooked-produce", (10_000_000, 10_000_000,
     "Produce that is essentially always cooked. Heating to about 158 F (70 C) "
     "inactivates Cyclospora, so the cooked food itself is not a route.")),
    ("non-produce", (10_000_000, 10_000_000,
     "Not a produce item. Cyclospora is not a meat, dairy, egg, grain or "
     "shelf-stable food pathogen - it does not occur in these foods. Any residual "
     "risk comes from a raw produce garnish or from a shared cutting board.")),
])

# (rank, name, icon, tier, note)
# Ordering approximates how commonly the food is eaten in the U.S.
FOODS = [
    (1, "Coffee", "drink", "non-produce", "Brewed with near-boiling water."),
    (2, "Milk", "dairy", "non-produce", None),
    (3, "Bread and rolls", "bread", "non-produce", "Baked."),
    (4, "Chicken", "meat", "non-produce", "Cooked to temperature."),
    (5, "Potatoes", "root", "cooked-produce", "Almost always cooked through."),
    (6, "Cheese", "dairy", "non-produce", None),
    (7, "Bananas", "fruit", "peeled", "The peel is discarded."),
    (8, "Eggs", "egg", "non-produce", None),
    (9, "Beef", "meat", "non-produce", None),
    (10, "Tomatoes", "tomato", "raw-firm", "Smooth skin rinses comparatively well."),
    (11, "Rice", "rice", "non-produce", "Boiled."),
    (12, "Apples", "fruit", "raw-firm", "Firm skin can be rinsed and rubbed."),
    (13, "Onions (cooked)", "onion", "cooked-produce", None),
    (14, "Pasta", "grain", "non-produce", "Boiled."),
    (15, "Sugar and sweeteners", "sweet", "non-produce", None),
    (16, "Breakfast cereal", "grain", "non-produce", None),
    (17, "Orange juice", "drink", "non-produce", "Pasteurized; fruit is peeled before pressing."),
    (18, "Pork", "meat", "non-produce", None),
    (19, "Butter and margarine", "dairy", "non-produce", None),
    (20, "Lettuce - iceberg", "leaf", "implicated", None),
    (21, "Corn (sweet, cooked)", "cooked-produce", "cooked-produce", None),
    (22, "Yogurt", "dairy", "non-produce", None),
    (23, "Soft drinks", "drink", "non-produce", None),
    (24, "Oranges", "fruit", "peeled", "The peel is discarded."),
    (25, "Turkey", "meat", "non-produce", None),
    (26, "Carrots (raw)", "root", "raw-firm", "Usually peeled or scrubbed hard."),
    (27, "Beer", "drink", "non-produce", None),
    (28, "Grapes", "berry", "raw-soft", "Eaten whole and unpeeled."),
    (29, "Peanut butter", "nut", "non-produce", "Roasted and ground."),
    (30, "Lettuce - romaine and leaf", "leaf", "implicated", None),
    (31, "Ice cream", "dairy", "non-produce", None),
    (32, "Watermelon", "fruit", "peeled",
     "Flesh is protected by the rind. Scrub the rind before cutting."),
    (33, "French fries", "cooked-produce", "cooked-produce", "Deep fried."),
    (34, "Bacon and sausage", "meat", "non-produce", None),
    (35, "Strawberries", "berry", "raw-soft", "Delicate surface; cannot be scrubbed."),
    (36, "Wine", "drink", "non-produce", None),
    (37, "Cooking oils", "non-produce", "non-produce", None),
    (38, "Tortillas", "bread", "non-produce", "Cooked on a griddle."),
    (39, "Beans (cooked, canned or dried)", "pod", "cooked-produce", None),
    (40, "Onions (raw)", "onion", "implicated", None),
    (41, "Cucumbers", "cucumber", "implicated", None),
    (42, "Peppers, bell (raw)", "tomato", "raw-firm", "Smooth skin rinses well."),
    (43, "Broccoli (cooked)", "cooked-produce", "cooked-produce", None),
    (44, "Apple juice", "drink", "non-produce", "Pasteurized."),
    (45, "Cabbage and coleslaw", "leaf", "raw-leafy", "Outer leaves are discarded; dense head."),
    (46, "Chocolate", "sweet", "non-produce", None),
    (47, "Tea", "drink", "non-produce", "Brewed with hot water."),
    (48, "Fish and seafood", "fish", "non-produce", None),
    (49, "Mushrooms (cooked)", "cooked-produce", "cooked-produce", None),
    (50, "Peaches and nectarines", "fruit", "raw-soft", "Fuzzy or soft skin, eaten unpeeled."),
    (51, "Pineapple", "fruit", "peeled", "Rind is removed."),
    (52, "Sweet potatoes", "root", "cooked-produce", None),
    (53, "Melon - cantaloupe and honeydew", "fruit", "peeled",
     "Rind removed, but scrub it first - the knife can carry contamination inward."),
    (54, "Blueberries", "berry", "raw-soft", "Eaten whole and unpeeled."),
    (55, "Avocado", "fruit", "peeled", "Skin and pit discarded."),
    (56, "Spinach", "leaf", "implicated", None),
    (57, "Crackers and chips", "snack", "non-produce", None),
    (58, "Pizza", "bread", "non-produce", "Baked; raw garnish is the only route."),
    (59, "Nuts and seeds", "nut", "non-produce", "Usually roasted."),
    (60, "Green beans (cooked)", "pod", "cooked-produce", None),
    (61, "Celery", "leaf", "raw-firm", "Ribbed surface, but firm enough to scrub."),
    (62, "Lemons and limes", "fruit", "peeled",
     "Juice and zest. Wash the peel if zesting or dropping a wedge in a drink."),
    (63, "Pears", "fruit", "raw-firm", "Firm skin can be rinsed and rubbed."),
    (64, "Cauliflower (cooked)", "cooked-produce", "cooked-produce", None),
    (65, "Peas (cooked)", "pod", "cooked-produce", None),
    (66, "Cilantro", "herb", "implicated", None),
    (67, "Salsa and pico de gallo", "tomato", "raw-firm",
     "Raw and often contains cilantro or onion - treat by its riskiest ingredient."),
    (68, "Raspberries and blackberries", "berry", "implicated", None),
    (69, "Garlic (cooked)", "cooked-produce", "cooked-produce", None),
    (70, "Squash and zucchini (cooked)", "cooked-produce", "cooked-produce", None),
    (71, "Deli meats", "meat", "non-produce", None),
    (72, "Soup (canned or cooked)", "cooked-produce", "non-produce", "Heated through."),
    (73, "Mayonnaise and dressings", "non-produce", "non-produce", "Shelf-stable, acidified."),
    (74, "Bagged salad mixes", "bag", "implicated", None),
    (75, "Cherries", "berry", "raw-soft", "Eaten whole and unpeeled."),
    (76, "Asparagus (cooked)", "cooked-produce", "cooked-produce", None),
    (77, "Grapefruit", "fruit", "peeled", "The peel is discarded."),
    (78, "Kale and chard", "leaf", "raw-leafy", "Often eaten raw in salads."),
    (79, "Plums", "fruit", "raw-soft", "Soft skin, eaten unpeeled."),
    (80, "Sweet corn (raw, in salads)", "cooked-produce", "raw-firm",
     "Uncooked kernels in salads and salsas do not get the benefit of heat."),
    (81, "Fresh parsley", "herb", "implicated", None),
    (82, "Fresh basil", "herb", "implicated", None),
    (83, "Mango", "fruit", "peeled", "Skin is removed."),
    (84, "Brussels sprouts (cooked)", "cooked-produce", "cooked-produce", None),
    (85, "Radishes", "root", "raw-firm", "Firm and scrubbable."),
    (86, "Snap peas and snow peas", "pod", "implicated", None),
    (87, "Beets (cooked)", "root", "cooked-produce", None),
    (88, "Arugula and mixed baby greens", "leaf", "raw-leafy",
     "Tender leaves, eaten raw, heavily handled in bagged form."),
    (89, "Kiwi", "fruit", "peeled", "Skin is usually removed."),
    (90, "Green onions and scallions (raw)", "onion", "raw-leafy",
     "Raw, layered structure that traps contamination between layers."),
    (91, "Eggplant (cooked)", "cooked-produce", "cooked-produce", None),
    (92, "Guacamole", "fruit", "raw-firm",
     "Avocado flesh is protected, but often mixed with raw onion and cilantro."),
    (93, "Coleslaw and prepared salads", "bag", "raw-leafy", "Raw, pre-shredded, heavily handled."),
    (94, "Hummus and dips", "non-produce", "non-produce", "Cooked chickpea base."),
    (95, "Fresh mint", "herb", "raw-herb", "Raw leafy herb, often used as a garnish."),
    (96, "Fresh dill", "herb", "raw-herb", "Raw leafy herb with a very fine, folded surface."),
    (97, "Sprouts (alfalfa, bean)", "herb", "raw-leafy",
     "Raw, grown warm and damp, and impossible to wash effectively."),
    (98, "Endive, radicchio and escarole", "leaf", "raw-leafy", "Raw salad leaves."),
    (99, "Watercress", "leaf", "raw-leafy", "Raw, grown in water, tender leaves."),
    (100, "Fresh chives", "herb", "raw-herb", "Raw herb garnish, added after cooking."),
]


def main():
    foods = json.loads((ROOT / "data" / "foods.json").read_text(encoding="utf-8"))
    # Map the 16 hand-authored entries onto their top-100 names.
    detailed = {f["name"]: f for f in foods["foods"]}
    alias = {
        "Lettuce - iceberg": "Non-recalled iceberg lettuce (whole head, retail)",
        "Lettuce - romaine and leaf": "Romaine lettuce",
        "Onions (raw)": "Onions (raw)",
        "Cucumbers": "Cucumbers",
        "Spinach": "Spinach",
        "Cilantro": "Cilantro",
        "Raspberries and blackberries":
            "Raspberries, blackberries and berry / fruit mixes",
        "Bagged salad mixes": "Bagged / packaged salad mixes containing iceberg",
        "Fresh parsley": "Fresh parsley",
        "Fresh basil": "Fresh basil",
        "Snap peas and snow peas": "Snap peas",
    }

    out, missing = [], []
    for rank, name, icon, tier, note in FOODS:
        entry = {"rank": rank, "name": name, "icon": icon}
        if tier == "implicated":
            src = detailed.get(alias.get(name, ""))
            if not src:
                missing.append(name)
                continue
            entry.update({
                "tier": "implicated",
                "scale": src["scale"],
                "basis": src["mitigation"],
                "detail_of": src["name"],
            })
        else:
            low, high, basis = TIERS[tier]
            entry.update({
                "tier": tier,
                "scale": {"low": low, "high": high},
                "basis": basis,
            })
        if note:
            entry["note"] = note
        out.append(entry)

    if missing:
        raise SystemExit(f"no detailed entry for: {missing}")

    doc = collections.OrderedDict([
        ("ordering_basis",
         "Ordering is an editorial approximation of how commonly each food is "
         "eaten in the United States, informed by USDA per-capita availability "
         "categories. It is not a published ranking - no agency publishes one in "
         "this form - and small differences in position are not meaningful."),
        ("risk_basis",
         "Risk is assigned by tier rather than per food, so two foods handled the "
         "same way cannot end up with different numbers. Foods that also appear in "
         "the detailed 16-food assessment use those figures directly."),
        ("key_point",
         "Cyclospora is spread by fresh produce and water. It is not a meat, dairy, "
         "egg, grain or shelf-stable food pathogen, and cooking destroys it. Most of "
         "this list is negligible-risk for that reason, not because the risk is "
         "merely small."),
        ("tiers", collections.OrderedDict(
            (k, {"low": v[0], "high": v[1], "basis": v[2]}) for k, v in TIERS.items())),
        ("foods", out),
    ])
    path = ROOT / "data" / "top100.json"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    tally = collections.Counter(f["tier"] for f in out)
    print(f"wrote {path.relative_to(ROOT)} with {len(out)} foods")
    for t, n in tally.most_common():
        print(f"  {t:16} {n}")


if __name__ == "__main__":
    main()
