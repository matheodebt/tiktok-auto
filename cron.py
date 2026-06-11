"""
Lance main.py tous les jours à 19h (heure Paris).
Déploie CE fichier comme point d'entrée sur Railway avec un cron job.
"""
import schedule
import time
import subprocess
import sys

def job():
    print("⏰ Lancement de la génération quotidienne...")
    result = subprocess.run([sys.executable, "main.py"], capture_output=False)
    if result.returncode != 0:
        print("❌ Erreur lors de l'exécution")
    else:
        print("✅ Génération terminée")

# Chaque jour à 19h00
schedule.every().day.at("19:00").do(job)

print("🕐 Scheduler démarré — prochaine vidéo à 19h00")
job()  # Lance une première fois au démarrage

while True:
    schedule.run_pending()
    time.sleep(60)
