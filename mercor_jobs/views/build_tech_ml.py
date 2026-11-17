"""Build tech_ml_jobs.html: full posting text for current tech & ML listings."""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
C = {j['title']: j for j in json.load(open(os.path.join(HERE, '..', 'mercor_jobs_current.json')))}
GROUPS = [
  ('ML & AI research', ['LLM Research Scientist (Pre-training & Computer Vision & Adversarial Robustness)',
     'Scientific / ML Engineer', 'MLOps Engineer, LLM Performance (Kernels, Profiling, Serving)',
     'GPU Kernel Expert', 'Trainium (NKI) Kernel Expert']),
  ('Software engineering', ['Senior Software Engineer, Backend (Node.js, TypeScript, Rust)',
     'Open Source Maintainer / Core Contributor – Software Engineer', 'Software Engineer — Agentic Search Systems',
     'Agent Engineer', 'Software Engineer (Foundational)', 'Embedded Systems / Kernel Engineer',
     'DevOps / Infrastructure Engineer', 'Engineering & Software Domain Expert',
     'Software Developers (Must own MacBook)', 'Customer Success Engineer (LatAm)', 'Customer Success Engineer (India)',
     'Software Engineer – Retail Investing Platforms (Paid Expert Interview)']),
  ('Security', ['CVE Vulnerability Expert', 'Responsible AI / Security Specialist', 'Cyber Engineer (3+ Years Experience)']),
  ('Task auditing & AI evals', ['SWE-Bench Task Auditor', 'ML Challenge Task Auditor', 'AI Developer Trace Task Auditor',
     'AWS Serverless & Infrastructure-as-Code Task Auditor', 'Kubernetes Task Auditor',
     'AI Evaluation Rubric Auditor', 'AI Evaluation Rubric Reviewer', 'Expert Interviewer']),
  ('Developer tool users', ['Application Users - Visual Studio Code on macOS - Code', 'Application Users - PyCharm on macOS - Code',
     'Application Users - Android Studio on macOS - Code', 'Application Users - VMware Fusion on macOS - Code',
     'Application Users - Quartus II on Windows - Code', 'Application Users - Linux Ubuntu 24.04 Expert - Professionals']),
]
UNIT = {'hourly': '/hr', 'per-task': '/task', 'one-time': ' one-time', 'yearly': '/yr'}
def pay(j):
    a, b = j['rateMin'], j['rateMax']
    if not a and not b: return 'Pay not listed'
    s = f"${a:,.0f}" if (a == b or not b) else f"${a:,.0f}–${b:,.0f}"
    return s + UNIT.get(j['payRateFrequency'], '')
out = []
for g, titles in GROUPS:
    for t in titles:
        j = C[t]
        out.append({'group': g, 'title': t, 'url': j['url'], 'pay': pay(j), 'rateMax': j['rateMax'] or 0,
                    'location': j['location'] or '', 'commitment': j['commitment'] or '',
                    'hours': j['hoursPerWeek'], 'slots': j['remainingSlots'], 'posted': (j['postedAt'] or '')[:10],
                    'referral': j['referralAmount'], 'text': j['fullPostingText']})
data = json.dumps(out, ensure_ascii=False).replace('</', '<\\/')
tpl = open(os.path.join(HERE, 'tech_ml_template.html')).read()
html = tpl.replace('__DATA__', data).replace('__COUNT__', str(len(out)))
open(os.path.join(HERE, 'tech_ml_jobs.html'), 'w').write(html)
print(len(out), 'jobs')
