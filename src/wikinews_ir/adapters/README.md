# Adapter Wikimedia — M5-A

`wikimedia.py` acquisisce o riproduce ranking Wikinotizie e riconcilia page ID
con il corpus M2. Test HTTP simulati, nessuna dipendenza dal percorso Web.
Il silver usa pacchetti e validazione in `evaluation/silver.py`, con una nuova
chat Codex avviata manualmente: nessun adapter API LLM.
