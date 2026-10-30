# Club STIM · Académie du numérique

Site officiel du Club STIM (Lycée Mixte 1 de Yamoussoukro) :
- **Accueil** : présentation du club et de ses départements
- **Formation** : socle obligatoire (10 modules), puis spécialité (informatique, robotique, IA, audio-visuel, design), avec évaluations et classement
- **Télécharger le guide** : PDF de 30 pages, pour lire hors connexion
- **Responsable** : tableau de bord des notes, placement et export CSV

## 1. Tester sur ton ordinateur

    pip install -r requirements.txt
    python app.py

Ouvre http://localhost:5000

Le code responsable par défaut est `changez-moi`. **Change-le avant la mise en ligne** (voir étape 3).

## 2. Mettre le projet sur GitHub

1. Sur github.com, clique sur **New repository**, nomme-le `club-stim-academie`, laisse-le **Private** si tu veux, puis crée-le.
2. Dans le dossier du projet, ouvre un terminal et tape :

       git init
       git add .
       git commit -m "Site officiel Club STIM"
       git branch -M main
       git remote add origin https://github.com/TON-NOM/club-stim-academie.git
       git push -u origin main

   Remplace `TON-NOM` par ton nom d'utilisateur GitHub. Le fichier `.gitignore` empêche d'envoyer la base de données.

## 3. Mettre le site en ligne (Render, gratuit)

1. Crée un compte sur render.com avec ton compte GitHub.
2. Clique sur **New + → Blueprint**, puis choisis le dépôt `club-stim-academie`. Render lit le fichier `render.yaml`.
3. Render demande les variables :
   - `ADMIN_CODE` : le code du responsable. Choisis-en un long, par exemple une phrase.
   - `NOTIF_TO` (facultatif) : ton adresse e-mail. Tu la recevras à chaque évaluation si tu configures aussi l'envoi d'e-mails (`SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`).
4. Clique sur **Apply**. Au bout de quelques minutes, le site est en ligne à une adresse `https://club-stim-academie.onrender.com` (ou similaire).

Pour mettre à jour : modifie le code, puis `git add .`, `git commit`, `git push`. Render redéploie tout seul.

## 4. Points importants

**Les données.** Les notes sont dans `data/academie.db`. Sur le plan gratuit de Render, le disque est **effacé à chaque redémarrage** : les notes disparaîtraient. Deux solutions :
- Télécharger une sauvegarde régulièrement depuis le tableau du responsable (bouton « Sauvegarder la base »), et la réinjecter si besoin.
- Ajouter un disque persistant chez Render (option payante), ou passer à une base PostgreSQL. C'est une modification que je peux faire pour toi.

**Le code responsable.** Il protège le tableau de bord. Ne le partage qu'aux personnes qui gèrent le club.

**Le PDF.** Il est dans `static/guide/`. Pour le mettre à jour, remplace le fichier en gardant le même nom.

**L'adresse de contact.** Modifie `templates/home.html` si tu veux afficher une adresse e-mail publique.

## 5. Modifier le bureau et le lien WhatsApp

- Le bureau est dans `bureau.json`. Modifie les noms, les fonctions et les contacts, puis fais un `git push`. Les postes marqués « À compléter » sont à renseigner.
- Le lien WhatsApp est défini dans `app.py` (variable `WHATSAPP_URL`). Il peut aussi être remplacé sans modifier le code grâce à la variable d'environnement `WHATSAPP_URL` sur Render.

## 6. Structure du projet

    app.py              serveur (routes, notes, classement, responsable)
    content.json        contenu de la formation (modules, quiz, ressources)
    templates/          pages (accueil, formation, téléchargement, responsable)
    static/             logo, styles, PDF du guide
    bureau.json         membres du bureau 2026-2027
    requirements.txt    bibliothèques Python
    render.yaml         configuration de déploiement Render
