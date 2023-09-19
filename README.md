# Hamster to Jira worklog sync

Synces worklogs from last X days from hamster time tracker to Jira.

- Jira parameters can be supplied through an .env file or as command line parameters
- hamster facts must start with Jira project tags. 
  For example, to add worklogs to this at this url
  [https://issues.apache.org/jira/browse/HADOOP-18909?filter=-4](https://issues.apache.org/jira/browse/HADOOP-18909?filter=-4)
  the hamster worklog should start with "HADOOP-18909"
- worklog start / end times are not preserved
- final summary lists all worklogs that could not be matched to Jira tickets 
- if in doubt, try with `--dry-run`

```bash
$ python3 hamster_jira.py --help
Succeeded in loading .env
usage: use "hamster_jira.py --help" for more information

Commit time to jira based on hamster time log For the updater to function, the
following variables have to be set in .env file or provided via command line
arguments: JIRA_SERVER_URL=https://<xxx>.atlassian.net
JIRA_USERNAME=john.doe@test.com JIRA_API_TOKEN=<jira api token>

optional arguments:
  -h, --help            show this help message and exit
  --jira-server-url JIRA_SERVER_URL
                        Jira server URL, overrides value from .env
  --jira-username JIRA_USERNAME
                        Jira username, overrides value from .env
  --jira-api-token JIRA_API_TOKEN
                        Jira api token, overrides value from .env
  --max-days-past MAX_DAYS_PAST
                        Max number of days in the past to look for timelogs
  --first-day FIRST_DAY
                        Ignore all days before this date
  --day-starts-at DAY_STARTS_AT
                        At which time the day starts
  --projects PROJECTS   Comma separated list of projects. If not supplied
                        obtained from jira
  --verbose             More logging
  --dry-run             Just print what you will do, do not change jira
```

Usage:
```bash
$ python3 hamster_jira.py --max-days-past=7 --verbose
```
will sync your worklogs from past 7 days into Jira.


