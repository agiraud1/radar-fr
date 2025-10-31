from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# Tes jobs réels
from scoring import recompute_daily

# Exemple de stub pour plus tard
def check_links():
    # TODO: implémenter la vérif des liens récents (lookback 7-14j)
    # Pour l’instant, un simple log:
    print("[check-links] running…")

def start_jobs(app):
    tz = pytz.timezone("Europe/Paris")
    sched = AsyncIOScheduler(timezone=tz)

    # 1) Score quotidien (06:00 CET/CEST)
    sched.add_job(recompute_daily, CronTrigger(hour=6, minute=0, timezone=tz), id="recompute-daily", replace_existing=True)

    # 2) Vérif des liens toutes les 3h
    sched.add_job(check_links, CronTrigger(minute=0, hour="*/3", timezone=tz), id="check-links", replace_existing=True)

    sched.start()
    print("[scheduler] jobs started")
