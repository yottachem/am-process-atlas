---
process: clip
author: Joshua Ritchey
date: 2026-11-13
refs:
  - cite: Tumbleston et al., Science 347, 1349 (2015)
    title: Continuous liquid interface production of 3D objects
    url: https://doi.org/10.1126/science.aaa2397
  - cite: US 11,174,326 B2 (University of Michigan)
    title: Polymerization photoinhibitor
    url: https://patents.google.com/patent/US11174326B2/en
  - cite: Konuray et al., Polymers 10, 178 (2018)
    title: State of the art in dual-curing acrylate systems
    url: https://doi.org/10.3390/polym10020178
---

Two things about CLIP are often misread.

First, oxygen inhibition is highly local. Oxygen keeps an uncured layer only about 10 to 100 µm thick at the window [1, 2]; the rest of the bath is ordinary resin. Over long builds, especially with engineering resins, exotherm runaway and rising viscosity become the problems, and they need engineering controls or resin formulation to manage. Hollow forms need drain holes and a plan for trapped resin and suction during the build.

Second, dual cure. UV-then-thermal curing is common in protective coatings, optical materials, and shape-memory polymers [3]. In SLA it is an option; in CLIP it is required, because the bake builds the network that sets the final properties.

Two practical gotchas. Minor defects or clouding on the window cut off the oxygen supply, and the part sticks to the cassette. And premixed two-part resins have a finite working window, so plan builds around it.
