# /jobagent eval

Evaluate a job against the candidate's CV using the Claude API A-F scoring system.

## Usage
```
/jobagent eval <job_id>
/jobagent eval <url>
```

## What it does
1. Reads cv.md
2. Fetches the job from jobs.db (or scrapes the URL)
3. Calls Claude API to score across 10 weighted dimensions
4. Returns: grade (A-F), numeric score (0-100), archetype, and 3-bullet gap analysis
5. Stores result in jobs.db

## API equivalent
```
POST /api/evaluate/<job_id>
```
