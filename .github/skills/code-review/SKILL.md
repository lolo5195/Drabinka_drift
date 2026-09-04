---
name: code-review
description: >-
  Reviews feature-branch pull requests for Drabinka_drift (drifting tournament
  results + TOP32 bracket app) against PLAN.md ticket Definition of Done before
  merge. Use when reviewing PRs, code review, merge readiness, feature tickets
  T-01..T-18, pytest, logic/rendering/ui layering, qualification sorting,
  bracket set_winner, or transparent PNG export.
---

# Code review — Drabinka_drift

Skill do **code review przed merem** brancha z kolejnym featurem z `PLAN.md`.
Źródło prawdy: `PLAN.md` + wymagania klienta. Nie akceptuj „prawie działa”.

## Cel review

Oceń, czy diff **domyka dokładnie jeden ticket** (T-0N) z DoD, nie psuje wcześniejszych milestone’ów i nie łamie architektury warstw.

## Workflow (wykonaj w tej kolejności)

1. **Zidentyfikuj ticket** — z tytułu PR / nazwy brancha / opisu (`T-04`, `feat/T-06-set-winner` itd.). Jeśli niejasne: wskaż to jako blocker i nie zgaduj zakresu.
2. **Przeczytaj DoD ticketu** w `PLAN.md` §3 (i powiązaną logikę w §2, pułapki w §4.1).
3. **Przejrzyj diff** pod checklistę uniwersalną + checklistę milestone’u (niżej).
4. **Sprawdź testy** — czy pokrywają DoD; czy stare testy nadal mają sens.
5. **Wydaj werdykt** w formacie poniżej. Brak zielonego DoD = **Request changes**.

## Format wyniku

```markdown
## Verdict: APPROVE | REQUEST CHANGES | NEEDS CLARIFICATION

**Ticket:** T-XX — <krótki tytuł z PLAN.md>
**Zakres PR:** <1–2 zdania: co faktycznie weszło>

### Critical (musi przed merem)
- …

### Suggestions
- …

### Nice to have
- …

### DoD check
- [x] / [ ] punkt DoD z PLAN.md — status + dowód (test / plik)

### Ryzyka / regresje
- …
```

**Critical** = naruszenie DoD, architektury warstw, tożsamości `Driver`, brak / złe testy, regresja wcześniejszego ticketu, „duch” w drabince, PNG ze screenshotu.
**Suggestion** = czytelność, nazewnictwo, brakujący edge case spoza DoD.
**Nice to have** = kosmetyka; nie blokuje merge’a.

## Checklist uniwersalna (każdy PR)

### Architektura

- [ ] `logic/` i `rendering/` **nie importują** niczego z `ui/`
- [ ] Logika sortowania / drabinki to czyste funkcje — da się przetestować bez NiceGUI
- [ ] Stan UI wyłącznie przez `AppState` (`ui/state.py`) — bez rozsianych globali (od T-08)
- [ ] PNG rysowane w Pillow na RGBA `(0,0,0,0)` — **nie** screenshot UI
- [ ] Drabinka trzyma **referencje `Driver`**, nigdy numer miejsca w tabeli
- [ ] `Driver` pozostaje `frozen=True`; `id` to stała tożsamość

### Zakres i jakość

- [ ] PR = jeden ticket (lub jasno uzasadniony mały follow-up); bez „przy okazji” UI/PNG w PR o logice
- [ ] Po tickecie program nadal się uruchamia (`python main.py` / odpowiednik z DoD)
- [ ] Typowanie: `Driver | None`, nie luźne `Any` / niejasne `object`
- [ ] Nazwy w kodzie **po angielsku**; teksty UI **po polsku**
- [ ] Brak hardcoded fontów systemowych — fonty z `assets/fonts/` (od T-13+)
- [ ] Brak sekretów, `.venv`, artefaktów builda w diffie

### Testy

- [ ] Nowe / zaktualizowane testy pokrywają **każdy punkt DoD** ticketu
- [ ] Nazwy plików: `tests/test_TXX.py` (konwencja repo)
- [ ] Edge case’e z `PLAN.md` §4.3, jeśli ticket ich dotyczy (0 / 1 / 10 / 32 zawodników, `(0,0)`, `(0,81)`, korekta zwycięzcy)
- [ ] Reviewer zakłada: `pytest` musi być zielony przed merem

## Domain rules — nie przepuszczaj naruszeń

Te reguły wynikają ze specyfikacji; błąd = Critical:

| Temat | Reguła |
| --- | --- |
| Sortowanie | `(-best, -worst)`; pełny remis → kolejność wpisania (stabilne `sorted`) |
| Zero | Tylko `(0,0)` → `is_zero`; `(0,81)` to wynik dodatni z best=81 |
| Puste pole | Przy **generowaniu** wyników puste = 0; wiersz bez nazwiska **pomijany** |
| Tabela 1–32 | Zawsze dokładnie 32 pozycje; braki = `None` → "-" |
| Tabela 33+ | Zera + nadmiar >32 dodatnich; numeracja od 33 |
| Seedy TOP32 | `SEED_PAIRS` z PLAN §2.2; pary sumują się do 33 |
| Przepływ | Zwycięzca meczu `i` → mecz `(i+1)//2` następnej rundy; slot góra/dół wg parzystości `i` |
| Półfinały | `T4_1`/`T4_2` → FINAL (winner) + PLAYOFF (loser); podium 1–4 jak w §2.3 |
| Korekta | Zmiana zwycięzcy → `clear_downstream` aż do podium; niezależne mecze nietknięte |
| Regeneracja drabinki | Jawna akcja z potwierdzeniem; nie auto-update po edycji kwalifikacji |
| Walkower | Zawodnik vs `None` = klik na zawodnika; `None` vs `None` nierozstrzygalny |

## Checklisty per milestone

Stosuj checklistę **aktualnego** ticketu + upewnij się, że wcześniejsze DoD nie są cofnięte.

### M0 — Fundament (T-01)

- Struktura katalogów zgodna z PLAN §1.2
- `requirements.txt` z nicegui≥3, pillow, pytest
- Smoke test + `main.py` startuje

### M1 — Silnik (T-02…T-07)

- **T-02:** properties `best`/`worst`/`is_zero`; `Driver` frozen
- **T-03:** przykład `(81,76)` > `(56,81)` > `(81,0)`; remis stabilny; `(0,81)` nie jak zero
- **T-04:** 28→pad None; zera w 33+; 0 zawodników; 35→3 w extra
- **T-05:** seedy T32_1/2/9; None przy 28 zawodnikach we właściwych slotach; `winner_goes_to` / `loser_goes_to` T4→PLAYOFF
- **T-06:** turniej „wyższy seed wygrywa” → FINAŁ 1v2 + podium; klik na `None` no-op; korekta czyści ścieżkę
- **T-07:** `cli_demo.py` przechodzi kwalifikacje→podium; złe inputy nie crashują

### M2 — UI kwalifikacji (T-08…T-10)

- **T-08:** 3 zakładki; stan tylko w `AppState`
- **T-09:** dynamiczne wiersze; wyniki 0–100 int; brak duplikatów przy szybkim wpisie
- **T-10:** kolejność = logika T-03/T-04; pogrubienie lepszego wyniku (przy równych — oba); 33+ tylko gdy potrzeba

### M3 — UI drabinki (T-11…T-12)

- **T-11:** układ skrzydeł + środek; "-" dla pustych; ostrzeżenie przy regeneracji
- **T-12:** klik → `set_winner`; UI = stan logiki; walkower; korekta czyści dalsze rundy w widoku; podium po FINAL/PLAYOFF

### M4 — PNG (T-13…T-15)

- **T-13/T-14:** RGBA, przezroczyste tło, fonty z repo (regular+bold osobne pliki), bez UI
- **T-15:** unikalne nazwy plików; działa dla pustej/częściowej drabinki

### M5 — Domknięcie (T-16…T-18)

- **T-16:** JSON z `schema_version`; zapis decyzji `(match_id, side)` i odtworzenie przez `set_winner`; „Nowe zawody” z potwierdzeniem
- **T-17:** native / pack — tylko jeśli w zakresie PR
- **T-18:** checklista §4.3 + README wystarczające dla osoby trzeciej

## Typowe czerwone flagi (od razu Critical)

1. Import `ui` / NiceGUI wewnątrz `logic/` lub `rendering/`
2. Sortowanie po sumie przejazdów zamiast (best, worst)
3. Miejsce w tabeli użyte jako ID zawodnika w drabince
4. `set_winner` bez `clear_downstream` (lub czyszczenie tylko jednego poziomu)
5. PNG przez `screenshot` / html2canvas / zrzut przeglądarki
6. Testy, które sprawdzają tylko happy path, a DoD wymaga konkretnych edge case’ów
7. Zmiana kontraktu modeli (`Driver`, `Match`, `TournamentBracket`) bez aktualizacji testów i miejsc użycia
8. Ticket UI mergowany przy czerwonych testach logiki z M1

## Czego nie robić w review

- Nie wymuszaj refaktorów poza zakresem ticketu, jeśli DoD jest spełnione
- Nie blokuj za styl kosmetyczny, jeśli konwencje repo są zachowane
- Nie akceptuj „dopiszemy testy później” — w tym projekcie testy **są** DoD
- Nie sugeruj zmiany stacku (Flet, FastAPI+HTML, Tkinter, DB) — decyzje są w PLAN §1.1
