# Template email

Firma e modello per le email inviate da `bending.forks.swe@gmail.com`.

| File | Contenuto |
|---|---|
| `firma-gmail.html` | Firma del gruppo: logo, nome, corso, università, email e sito |
| `modello-generico.html` | Modello di email con saluto, testo, chiusura e firma |
| `modello-generico.txt` | Lo stesso modello in testo semplice |
| `anteprima.png` | Anteprima del modello |

Il logo è caricato da `assets/logo-bending-forks-trasparente.png` di questa repository tramite il link
`https://raw.githubusercontent.com/bendingforksswe/documenti-swe/main/assets/logo-bending-forks-trasparente.png`.
Gmail mostra solo immagini con un indirizzo pubblico: il file non va spostato o rinominato e la repository
deve restare pubblica, altrimenti il logo sparisce dalle firme.

## Installare la firma in Gmail

1. Aprire `firma-gmail.html` con il browser, premere Ctrl+A e poi Ctrl+C.
2. In Gmail: Impostazioni, "Visualizza tutte le impostazioni", scheda "Generali", sezione "Firma".
3. "Crea nuova", nome `Bending Forks`, incollare con Ctrl+V.
4. In "Impostazioni predefinite per la firma" scegliere `Bending Forks` per i nuovi messaggi e per risposte e inoltri.
5. Premere "Salva modifiche" in fondo alla pagina.

## Salvare il modello in Gmail

1. Impostazioni, scheda "Avanzate", attivare "Modelli" e salvare.
2. Aprire `modello-generico.html` con il browser, copiarlo e incollarlo in una nuova email (senza la firma, che Gmail aggiunge da sola).
3. Nella finestra di scrittura: tre puntini, "Modelli", "Salva bozza come modello", "Salva come nuovo modello".
4. Per usarlo: nuova email, tre puntini, "Modelli", scegliere il modello e sostituire le parti tra `[ ]`.

## Regole

- Oggetto con il prefisso `[Ingegneria del Software]`.
- "Buongiorno" o "Buon pomeriggio", testo breve, "Cordiali saluti," e "Team Bending Forks", poi la firma.
