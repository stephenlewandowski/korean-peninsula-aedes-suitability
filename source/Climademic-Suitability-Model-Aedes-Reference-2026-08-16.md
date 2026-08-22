**# Climademic Suitability Model — Aedes habitat reference**

\- Saved: 2026-08-16

\- Source signal: Christopher Irrgang LinkedIn post

\- Status: research reference; potential data application

\- Domains: climate and health; vector-borne disease; spatial epidemiology; machine learning; public-health surveillance; open science

**## Verified reference links**

\- LinkedIn author: [Christopher Irrgang]\(https\://www\.linkedin.com/in/christopherirrgang/)

\- LinkedIn post: [Climademic Suitability Model now available on GitHub]\(https\://www\.linkedin.com/posts/christopherirrgang\_climatechange-publichealth-aedes-activity-7493953932462006272-g7xM)

\- Paper: [Suitable seasons: Global monthly habitat suitability for the arbovirus vectors *\*Aedes aegypti\** and *\*Aedes albopictus\** in 1975–2024]\(https\://doi.org/10.64898/2026.04.17.719149)

\- bioRxiv record: [Preprint landing page]\(https\://www\.biorxiv.org/content/10.64898/2026.04.17.719149)

\- GitHub: [ClimSocAna/climademic\_suitability\_model]\(https\://github.com/ClimSocAna/climademic\_suitability\_model)

\- Dataset: [Zenodo record 21924442]\(https\://zenodo.org/records/21924442)

The GitHub repository identifies Zenodo record 21924442 as the current full habitat-suitability dataset. Prefer this repository-linked record over older search-indexed Zenodo records unless the authors document a newer version.

**## What the resource contains**

The Climademic Suitability Model estimates monthly global habitat suitability for *\*Aedes aegypti\** and *\*Aedes albopictus\** on a 0.25° × 0.25° grid from 1975 through 2024. The workflow combines One-Class Support Vector Machines with incremental learning. A base model is trained on historical climate, land-use, population, and mosquito-occurrence data, then updated annually with newer occurrence observations.

The code repository is public and MIT-licensed. As of 2026-08-16, it contains procedural Python scripts and Jupyter notebooks rather than a packaged application. Its README identifies current implementation limits, including dependence of the GMOD preparation step on the global inference dataset and fixed global grid limits.

The linked paper is a preprint and should not be treated as peer-reviewed final evidence. Habitat suitability is not equivalent to mosquito abundance, confirmed vector presence, infection prevalence, or human transmission risk. Any applied analysis should also examine surveillance coverage, occurrence-reporting bias, probability calibration, spatial resolution, temporal autocorrelation, and the distinction between environmental change and dispersal or sampling effects.

Identity check: this resource models mosquito habitat suitability. It is not a ranking model for climate-focused academic locations.

**## Possible data applications**

1\. **\*\*Korea–Japan seasonal suitability trends.\*\*** Extract a public, non-installation-specific regional subset and compare monthly suitability, season onset, season end, and suitable-season length across 1975–1984, 1995–2004, and 2015–2024.

2\. **\*\*Population exposure.\*\*** Overlay gridded population estimates to examine how many people live in areas with increasing suitability or longer suitable seasons. Keep this distinct from disease incidence or individual risk.

3\. **\*\*Climate–vector–disease comparison.\*\*** Compare suitability with publicly available dengue, chikungunya, or Zika surveillance while explicitly testing lags and reporting changes. Use suitability as one input, not as a disease forecast by itself.

4\. **\*\*Heat, humidity, and urbanization analysis.\*\*** Assess how temperature, dew point, land use, and population growth relate to changing suitability, with attention to correlated predictors and the paper's explainability results.

5\. **\*\*Early-warning prototype.\*\*** Test whether recent suitability estimates add predictive value beyond seasonal baselines and conventional climate indicators. Require out-of-sample validation, calibration, uncertainty display, and a clear decision threshold before presenting it as operational early warning.

6\. **\*\*Teaching product.\*\*** Build a reproducible senior-level case on ecological-niche modelling, surveillance bias, model interpretation, and the difference between environmental suitability and public-health consequence.

**## Recommended first application**

Begin with a static Korea–Japan regional table and map rather than a dashboard. Calculate monthly suitability and suitable-season length for each species, compare early and recent decades, and document the extraction, aggregation, missingness, and uncertainty. Add a time slider or location selector only if it helps users compare a defined geography or period without implying unsupported precision.

**## Korean Peninsula / North Korea and an** *\*Anopheles\** **extension**

This is a useful follow-on, but it is a new model branch rather than a parameter rename. The current repository is Aedes-specific in several places: \`config.json\` contains hyperparameters only for \`aegypti\` and \`albopictus\`, and the training workflow filters the training data with an \`Aedes \<species>\` label. The repository's monthly covariates (temperature, dew point, precipitation, wind, population, and land-use classes) are a plausible starting feature set, but an *\*Anopheles\** model needs species-specific occurrence/abundance data, labels, calibration, and validation.

The first target should be *\*Anopheles sinensis\**. CDC describes it as the presumed primary malaria vector on the Korean peninsula, and the Korea Disease Control and Prevention Agency (KDCA) lists *\*An. sinensis\**, *\*An. kleini\**, *\*An. pullus\**, *\*An. lesteri\**, *\*An. belenrae\**, *\*An. sineroides\**, *\*An. koreicus\**, and *\*An. lindesayi\** in the Republic of Korea; seven of those eight are described as malaria-capable. [CDC EID peninsula context]\(https\://wwwnc.cdc.gov/eid/article/4/2/98-0219\_article) · [KDCA 2024 vector-surveillance report]\(https\://www\.kdca.go.kr/bbs/chungcheong/142/293598/download.do) · [WHO 2024 Republic of Korea profile]\(https\://cdn.who.int/media/docs/default-source/country-profiles/malaria/malaria-2024-kor.pdf?download=true&sfvrsn=6738dd63\_4)

**### Data and validation leads**

\- **\*\*KDCA surveillance:\*\*** the 2025 report documents a ROK surveillance programme running since 2009, with seasonal abundance and *\*Plasmodium vivax\** infection testing in malaria-risk areas. It is a strong validation/response-data lead, but it is ROK surveillance, not direct DPRK coverage.

\- **\*\*Goyang time series:\*\*** the open PLOS study provides 2008–2012 *\*An. sinensis\** surveillance from 12 permanent traps (9,512 female mosquitoes), with supporting XLSX datasets and climate covariates. It is suitable for a small feasibility notebook and seasonal validation, while its authors caution that morphological identification can conflate closely related anophelines. [Jang & Chun, PLOS One (2020)]\(https\://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0244479)

\- **\*\*Occurrence records:\*\*** query GBIF and Korean specimen datasets for *\*Anopheles\** records, retaining coordinates, collection date, taxonomic basis, license, and sampling effort. Treat opportunistic occurrence points and trap abundance as different observation types; do not merge them without an explicit observation model.

**### North Korea scope and caveat**

The initial map can cover the full Korean Peninsula and DMZ-adjacent region using the same environmental grid, but any DPRK result should be labelled **\*\*modeled extrapolation\*\*** unless direct DPRK occurrence or surveillance records are secured. Show an uncertainty or extrapolation flag alongside suitability; do not present it as observed mosquito presence, malaria incidence, or a military/site-risk map. Keep the first release at public regional/grid aggregation and exclude sensitive installation-level locations.

**### Minimal, source-linked MVP**

1\. Build a static peninsula table and diagram for *\*An. sinensis\**: monthly suitability, first/last suitable month, and suitable-season length for historical versus recent periods.

2\. Train and evaluate on public ROK occurrence/trap data, with spatial and temporal holdouts rather than random-only splits.

3\. Project the fitted model across the peninsula, separating ROK validation cells from DPRK extrapolation cells and displaying uncertainty.

4\. Compare suitability against public malaria/vector surveillance only after checking lag structure; suitability is not abundance, infection, or human transmission risk.

Next technical step: audit the repository's data schema and build a small ROK-only *\*An. sinensis\** feasibility notebook before producing a peninsula-wide map. Do not claim that the current Aedes outputs answer the *\*Anopheles\** question.

**## Original post supplied by the user**

\> Climademic Suitability Model now available on GitHub!

\>

\> Today, we release the training and inference framework behind our Climademic Suitability Model.

\>

\> The models estimate global habitat suitability for the two most important arbovirus vectors, Aedes aegypti and Aedes albopictus, at monthly resolution on a 0.25° × 0.25° grid, covering the last 50 years!

\>

\> Methodologically, we combine One-Class Support Vector Machines with an incremental learning strategy: the base model is trained on historical climate, land-use, and population data, then updated year by year with new mosquito occurrence observations; keeping the model's picture of each species' ecological niche continuously up to date.

\>

\> Why this matters: As the climate changes, the habitats of these vectors are shifting and with them also transmission risk for dengue, Zika, chikungunya, and more. Reliable, up-to-date suitability maps are an important foundation for early-warning systems and public health planning.

\>

\> How can such data be used? For instance, we can now examine mosquito habitat and human living-environments with unprecedented spatio-temporal detail (see figure from the pre-print). Other examples are transmission risk modelling and climate-driven outbreak analyses.

\>

\> Code & workflow via Github: https\://lnkd.in/dK\_vcPx2

\>

\> Full dataset via Zenodo: https\://lnkd.in/dk3TmkMt

\>

\> We'd love your feedback, welcome collaborations, and encourage anyone interested to use the workflow for their own analyses.

\>

\> And, of course, a big shout-out the Climademic team: Dr. Tarique Siddiqui, Nadezhda Malysheva, Anna-Maria Hartner, Diogo Parreira, and Jakob-Wendelin Genger.

\>

\> #ClimateChange #PublicHealth #Aedes #VectorBorneDisease #OpenScience #MachineLearning #GlobalHealth #ClimateAndHealth

**## Retrieval notes**

\- The LinkedIn post and stable resource links were checked on 2026-08-16.

\- The GitHub repository was created in August 2026 and may change; use its commit history and environment files for reproducibility.

\- Confirm the Zenodo record's version, file inventory, size, checksum, and license before downloading or reusing the full dataset.

\- Preserve the preprint DOI, dataset record, code commit, retrieval date, geographic subset, and all transformations in any derivative analysis.