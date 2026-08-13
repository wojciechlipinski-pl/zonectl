# TODO / FIXME / HACK / XXX

## Bieżący zakres 4.8

- [x] Odczytowa autodetekcja konfiguracji BIND i aktywnej integracji RPZ.
- [ ] Test produkcyjnego raportu `zctl bind environment-report` bez zmian w BIND.
- [ ] Kreator pierwszego uruchomienia i plan bezpiecznego importu konfiguracji.
- [x] Odczytowy status CERT RPZ pod F3 z zachowaniem liczbowego wieku.
- [x] Włączyć szczegóły strefy i RPZ do responsywnego dwupanelowego ekranu głównego.
- [ ] Dopolerować semantykę kolorów i hierarchię nagłówków prawego panelu.
- [ ] Przetestować kontrakt wizualny w PuTTY z `xterm-256color`, fontem
  monospace 12–14 pt oraz w bezpiecznym trybie fallback 8 kolorów.
- [ ] Opcjonalny, transakcyjny profil `MANAGED` dla aktualizatora CERT RPZ.
- [ ] Pierwszy etap panelowej przebudowy TUI zgodnej z koncepcją 4.8.
## Pierwsze uruchomienie

- [x] Rozpoznanie istniejącej konfiguracji BIND i klasyfikacja zasobów.
- [x] Odczytowy ekran gotowości w TUI (F2).
- [x] Plan i dry-run importu wybranej strefy legacy.
- [x] Transakcyjny import uruchamiany wyłącznie decyzją operatora (F6).
- [x] Rozbicie zbiorczego stanu BLOCKED na konkretne kategorie.
