# apps/cclms/cclms/patches/scheduled_tasks.py
from cclms.utils.atm_lead_cleaner import clean_atm_leads

def daily_atm_leads_clean():
    clean_atm_leads()
