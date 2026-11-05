# Reproducibility report

Seed `20261022`. Each scale is generated twice in separate Python processes and every output file is compared by SHA-256 (first 16 hex characters shown; the comparison uses the full hash).

## Scale `starter`

Command (run twice): `python -m hrgen --scale starter --seed 20261022 --out <folder>`

| File | Rows | SHA-256 run 1 | SHA-256 run 2 | Match |
|---|---|---|---|---|
| assignment.csv | 519 | 5c091791c9068b7d | 5c091791c9068b7d | yes |
| assignment.json |  | b3b13b6f7105342c | b3b13b6f7105342c | yes |
| category.csv | 6 | 4ee761735ea4503a | 4ee761735ea4503a | yes |
| category.json |  | 978b8da1e238a3ab | 978b8da1e238a3ab | yes |
| department.csv | 8 | d0f68905cd40547a | d0f68905cd40547a | yes |
| department.json |  | ff36204afa7a6449 | ff36204afa7a6449 | yes |
| employee.csv | 200 | d9a563f671369506 | d9a563f671369506 | yes |
| employee.json |  | 65687abb12c61814 | 65687abb12c61814 | yes |
| ground_truth/expected_decisions.csv | 500 | 285ad24a3168b8bb | 285ad24a3168b8bb | yes |
| ground_truth/expected_decisions.json |  | c9af460273418727 | c9af460273418727 | yes |
| ground_truth/ground_truth.csv | 30 | 48bca2da6c48cd99 | 48bca2da6c48cd99 | yes |
| ground_truth/ground_truth.json |  | bcf2337b2f7ab3d3 | bcf2337b2f7ab3d3 | yes |
| kb_policy_version.csv | 41 | b707017f6563de9c | b707017f6563de9c | yes |
| kb_policy_version.json |  | ffaf65f79757c5e4 | ffaf65f79757c5e4 | yes |
| knowledge_article.csv | 30 | 941a6850e046a645 | 941a6850e046a645 | yes |
| knowledge_article.json |  | 2bde853921eb1714 | 2bde853921eb1714 | yes |
| manifest.json |  | 112671811b15c897 | 112671811b15c897 | yes |
| message.csv | 2000 | 99a52daece1d91de | 99a52daece1d91de | yes |
| message.json |  | de94be217d55866d | de94be217d55866d | yes |
| message_citation.csv | 481 | 973c9abe7cde9269 | 973c9abe7cde9269 | yes |
| message_citation.json |  | 437edd76f6b7a1d8 | 437edd76f6b7a1d8 | yes |
| metrics.json |  | d087b9f90abb6543 | d087b9f90abb6543 | yes |
| policy_document.csv | 12 | b2b7cac1965d8bb9 | b2b7cac1965d8bb9 | yes |
| policy_document.json |  | 619f340bae77d91b | 619f340bae77d91b | yes |
| policy_version.csv | 33 | 57e08e7e90eaa1bf | 57e08e7e90eaa1bf | yes |
| policy_version.json |  | c1e1e023e0e6ea04 | c1e1e023e0e6ea04 | yes |
| resolution.csv | 500 | 36a1b39867eb38aa | 36a1b39867eb38aa | yes |
| resolution.json |  | 848732b6e3176ca0 | 848732b6e3176ca0 | yes |
| seed.sql |  | 7fe8fcf8fc35a3c3 | 7fe8fcf8fc35a3c3 | yes |
| sla.csv | 500 | ac924be99a19eaef | ac924be99a19eaef | yes |
| sla.json |  | f443f8c09bf65320 | f443f8c09bf65320 | yes |
| ticket.csv | 500 | fea63e38faabff36 | fea63e38faabff36 | yes |
| ticket.json |  | f224805d3c8bed4e | f224805d3c8bed4e | yes |
| ticket_status_event.csv | 2590 | c19b978728a9578b | c19b978728a9578b | yes |
| ticket_status_event.json |  | 3e09bcbd51d556f4 | 3e09bcbd51d556f4 | yes |
| validation_summary.md |  | 81f81e33b4383db5 | 81f81e33b4383db5 | yes |

Files compared: 36. Verdict for `starter`: **IDENTICAL**

## Scale `full`

Command (run twice): `python -m hrgen --scale full --seed 20261022 --out <folder>`

| File | Rows | SHA-256 run 1 | SHA-256 run 2 | Match |
|---|---|---|---|---|
| assignment.csv | 5125 | 7643a5470872bf79 | 7643a5470872bf79 | yes |
| assignment.json |  | 66384dea5219ed1c | 66384dea5219ed1c | yes |
| category.csv | 6 | 4ee761735ea4503a | 4ee761735ea4503a | yes |
| category.json |  | 978b8da1e238a3ab | 978b8da1e238a3ab | yes |
| department.csv | 12 | f195ad31ffa11c7f | f195ad31ffa11c7f | yes |
| department.json |  | 670569269957092b | 670569269957092b | yes |
| employee.csv | 1200 | 2a24986782bf576d | 2a24986782bf576d | yes |
| employee.json |  | b97f61f89506be3f | b97f61f89506be3f | yes |
| ground_truth/expected_decisions.csv | 5000 | f13a1928f7b54004 | f13a1928f7b54004 | yes |
| ground_truth/expected_decisions.json |  | ed67252cb5d5f724 | ed67252cb5d5f724 | yes |
| ground_truth/ground_truth.csv | 283 | 844315845bc56249 | 844315845bc56249 | yes |
| ground_truth/ground_truth.json |  | b1184f07a9ffddd4 | b1184f07a9ffddd4 | yes |
| kb_policy_version.csv | 199 | 42c9cd449224ad5a | 42c9cd449224ad5a | yes |
| kb_policy_version.json |  | 7e30b2ed9ffc03e9 | 7e30b2ed9ffc03e9 | yes |
| knowledge_article.csv | 150 | 60a80f4cb2b50cb6 | 60a80f4cb2b50cb6 | yes |
| knowledge_article.json |  | 4ce2a3f2001913cc | 4ce2a3f2001913cc | yes |
| manifest.json |  | ef8e62773bb6de43 | ef8e62773bb6de43 | yes |
| message.csv | 20000 | 5cc9df46854f9925 | 5cc9df46854f9925 | yes |
| message.json |  | aeefa1b71949e8a7 | aeefa1b71949e8a7 | yes |
| message_citation.csv | 4854 | e53dbdab6c58749b | e53dbdab6c58749b | yes |
| message_citation.json |  | 4657d523f8c9f343 | 4657d523f8c9f343 | yes |
| metrics.json |  | c1a1cc64e699c157 | c1a1cc64e699c157 | yes |
| policy_document.csv | 40 | ea7415e7f9d3ef76 | ea7415e7f9d3ef76 | yes |
| policy_document.json |  | b94a189134f3d9ec | b94a189134f3d9ec | yes |
| policy_version.csv | 105 | 4a84839c77e9d258 | 4a84839c77e9d258 | yes |
| policy_version.json |  | ea5eeba93a4eab8c | ea5eeba93a4eab8c | yes |
| resolution.csv | 5000 | 73f6e891ee15aede | 73f6e891ee15aede | yes |
| resolution.json |  | d906f18704feb877 | d906f18704feb877 | yes |
| seed.sql |  | ff3a1f44e7b5b53a | ff3a1f44e7b5b53a | yes |
| sla.csv | 5000 | 2f7d2a0ca30cddc8 | 2f7d2a0ca30cddc8 | yes |
| sla.json |  | 3d3d28e86d5b80cf | 3d3d28e86d5b80cf | yes |
| ticket.csv | 5000 | 9e3dddbaf5e688ff | 9e3dddbaf5e688ff | yes |
| ticket.json |  | d83394a5ab4de9ce | d83394a5ab4de9ce | yes |
| ticket_status_event.csv | 25943 | 71a57fbe02e9e774 | 71a57fbe02e9e774 | yes |
| ticket_status_event.json |  | eb70cd783efcb253 | eb70cd783efcb253 | yes |
| validation_summary.md |  | 5545dd21c08f5624 | 5545dd21c08f5624 | yes |

Files compared: 36. Verdict for `full`: **IDENTICAL**

## Overall verdict: **IDENTICAL**
