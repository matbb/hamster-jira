#!/usr/bin/env python3
import os
import dotenv
import sqlite3
import re
import argparse
import sys
import datetime
import dateutil
from jira import JIRA
import pandas as pd
import warnings

warnings.simplefilter(action="ignore", category=pd.errors.PerformanceWarning)


# Program arguments
parser = argparse.ArgumentParser(
    description="""Commit time to jira based on hamster time log
    
    For the updater to function, the following variables have to be set in .env file
    or provided via command line arguments:

    JIRA_SERVER_URL=https://<xxx>.atlassian.net
    JIRA_USERNAME=john.doe@test.com
    JIRA_API_TOKEN=<jira api token>
    """,
    usage='use "%(prog)s --help" for more information',
)

parser.add_argument(
    "--jira-server-url",
    type=str,
    default=None,
    help="""Jira server URL, overrides value from .env""",
)

parser.add_argument(
    "--jira-username",
    type=str,
    default=None,
    help="""Jira username, overrides value from .env""",
)

parser.add_argument(
    "--jira-api-token",
    type=str,
    default=None,
    help="""Jira api token, overrides value from .env""",
)

parser.add_argument(
    "--max-days-past",
    type=int,
    default=14,
    help="""Max number of days in the past to look for timelogs""",
)


def date_verifier(s):
    try:
        date = datetime.datetime.strptime(s, "%Y-%m-%d")
    except Exception as e:
        raise argparse.ArgumentTypeError("Error converting " + str(s) + ", " + str(e))
    return date


parser.add_argument(
    "--first-day",
    type=date_verifier,
    default=None,
    help="""Ignore all days before this date""",
)

parser.add_argument(
    "--day-starts-at",
    type=str,
    default="5:00",
    help="""At which time the day starts""",
)

parser.add_argument(
    "--projects",
    type=list,
    default=None,
    help="""Comma separated list of projects. If not supplied obtained from jira""",
)

parser.add_argument(
    "--verbose",
    action="store_true",
    default=False,
    help="""More logging""",
)

parser.add_argument(
    "--dry-run",
    action="store_true",
    default=False,
    help="""Just print what you will do, do not change jira""",
)


def agg_name(names):
    return "\n".join(sorted(set(names)))


def update_jira_worklog(
    jira: JIRA,
    day: datetime.date,
    project: str,
    issue_number: int,
    df_all: pd.DataFrame,
    verbose=False,
    dry_run=False,
):
    if verbose:
        vprint = print
    else:

        def vprint(*args, **kwargs):
            pass

    day = datetime.datetime.combine(day, datetime.time(hour=0, minute=0))
    w = df_all["day"] == day
    w = w & (df_all["project"] == project)
    w = w & (df_all["issue_number"] == issue_number)
    df = df_all.loc[w]

    df_hamster = df.loc[df["source"] == "hamster"]
    df_jira = df.loc[df["source"] == "jira"]

    t_hamster = df_hamster["duration"].sum()
    t_jira = df_jira["duration"].sum()

    issue_key = f"{project}-{issue_number}"
    if abs((t_hamster - t_jira).total_seconds()) < 10:
        vprint(f"Worklogs for issue {issue_key} are in sync")
    else:
        if verbose:
            vprint(f"Dataframe : {len(df)}")
            vprint(df)
        vprint(day.strftime("%a %m %d"))
        vprint("Jira : ", t_jira)
        vprint("Hamster : ", t_hamster)
        vprint("Times differ")
        tz_local = df_hamster["start_time"].iloc[0].tz
        for w_id in df_jira["log_id"].tolist():
            vprint(f"Deleting worklog {w_id} in jira issue {issue_number}")
            if not dry_run:
                w = jira.worklog(issue=issue_key, id=w_id)
                w.delete()
        desc = "\n\n".join(
            [desc for desc in df_hamster["description"].to_list() if len(desc) > 0]
        )
        vprint(f"Adding worklog to jira issue {issue_number}: \n{desc}")
        if not dry_run:
            w = jira.add_worklog(
                issue=issue_key,
                timeSpentSeconds=t_hamster.total_seconds(),
                started=day.replace(hour=12, minute=34, tzinfo=tz_local),
                comment=desc,
            )
            w.update()

    return df_hamster, df_jira, df

    total_jira = df[df["source"] == "jira"]["duration"].sum()
    total_hamster = df[df["source"] == "hamster"]["duration"].sum()
    # display( df[columns2])
    display(df_gb)
    return df_gb


if __name__ == "__main__":
    if dotenv.load_dotenv(".env"):
        print("Succeeded in loading .env")
    args = parser.parse_args()
    if args.dry_run:
        print("Dry run: just printing what would be done")

    """
    Algorithm:
    1) find all issues from hamster in timeframe
    2) find all issues in jira with timelog entries from me in timeframe
    all_issues = issues from hamster + issues from jira

    3) download all worklogs from all issues

    3) for each day in time frame:
        - go through all issues where there is some work on the issue in hamster logs or in jira 
        push hamster time to jira:
            if the time reported in jira is different than the time reported in hamster, delete all worklogs from that day
            and issue a single worklog for total time with concatenated all comments on that day.
            Set "started" to 12.34 

    4) report all worklogs that are in hamster but not in jira (where ticket could not be found for example)
    """

    jira_server_url = os.environ.get("JIRA_SERVER_URL", None) or args.jira_server_url
    jira_username = os.environ.get("JIRA_USERNAME", None) or args.jira_username
    jira_api_token = os.environ.get("JIRA_API_TOKEN", None) or args.jira_api_token

    if None in {jira_server_url, jira_username, jira_api_token}:
        print(
            "Error: jira server url, username and api_token have to be provided either through .env or command line"
        )
        sys.exit(1)
    jira = JIRA(
        server=jira_server_url,
        basic_auth=(jira_username, jira_api_token),
    )
    hamster_fname = ".local/share/hamster/hamster.db"
    db = sqlite3.connect(os.environ["HOME"] + "/" + hamster_fname)
    tz_local = dateutil.tz.tzlocal()
    day_start = datetime.datetime.strptime(args.day_starts_at, "%H:%M").replace(
        year=2000, month=1, day=1, tzinfo=tz_local
    )

    dt_cutoff = datetime.datetime.now() - datetime.timedelta(days=args.max_days_past)
    dt_cutoff = datetime.datetime(
        year=dt_cutoff.year,
        month=dt_cutoff.month,
        day=dt_cutoff.day,
        hour=day_start.hour,
        minute=day_start.minute,
        tzinfo=tz_local,
    )

    print("Initialization ok")
    print("Synchronizing worklogs from ", dt_cutoff, " onwards")

    jira_user_id = jira.current_user()
    if args.projects:
        projects = args.projects.split(",")
    else:
        projects = jira.projects()
        projects = [project.key for project in projects]

    # Issue search patterns are built from project list
    projects = "|".join(projects)
    issue_re = (
        r"^(.*[ :])?" + r"(?P<project>" + projects + r")\-(?P<number>[0-9]*)([ :-].*)?$"
    )

    df_hamster = pd.read_sql(
        """ SELECT 
            facts.id AS log_id,
            *
        FROM 
            facts AS facts
        JOIN 
            activities AS activities
        ON
            facts.activity_id = activities.id
        ORDER BY
            facts.start_time
        DESC
        ;
            """,
        con=db,
    )
    for col in ["start_time", "end_time"]:
        df_hamster[col] = pd.to_datetime(df_hamster[col])

    columns = ["log_id", "start_time", "end_time", "name", "description"]
    df_hamster = df_hamster[columns]

    for col in ["start_time", "end_time"]:
        df_hamster[col] = df_hamster[col].apply(lambda dt: dt.replace(tzinfo=tz_local))

    df_hamster["duration"] = df_hamster["end_time"] - df_hamster["start_time"]

    def get_ticket_key(row):
        activity_name = row["name"]
        m = re.match(issue_re, activity_name)
        if m is not None:
            return m.groupdict()["project"], int(m.groupdict()["number"])
        return None, 0

    df_hamster[["project", "issue_number"]] = df_hamster.apply(
        get_ticket_key, result_type="expand", axis="columns"
    )

    df_hamster["issue_number"] = df_hamster["issue_number"].astype(int)

    def get_day(start_time):
        time_in_day = start_time.replace(year=2000, month=1, day=1)
        day = datetime.datetime.combine(
            start_time.date(), datetime.time(hour=0, minute=0)
        )
        if time_in_day < day_start:
            day = day - datetime.timedelta(days=1)
        return day.replace(tzinfo=None)
        return day.replace(tzinfo=tz_local)

    df_hamster["day"] = df_hamster["start_time"].apply(get_day)

    df_hamster = df_hamster.loc[df_hamster["start_time"] > dt_cutoff]

    jql = f"""worklogAuthor = {jira_user_id} AND worklogDate >= "{dt_cutoff.strftime("%Y-%m-%d")}" """
    issues = jira.search_issues(jql, maxResults=False)

    row_list = []
    row_columns = [
        "log_id",
        "project",
        "issue_number",
        "name",
        "start_time",
        "duration",
    ]

    print("Parsing worklogs from ", len(issues), "issues: start")
    for issue in issues:
        worklogs = jira.worklogs(issue)
        for w in worklogs:
            if w.author.accountId != jira_user_id:
                continue
            row = (
                w.id,
                issue.get_field("project").key,
                int(issue.key.split("-")[1]),
                issue.get_field("summary"),
                pd.to_datetime(w.started),  # .replace(tzinfo=None),
                datetime.timedelta(seconds=w.timeSpentSeconds),
            )
            row_list.append(row)
    print("Parsing worklogs from ", len(issues), "issues: finished")

    df_jira = pd.DataFrame(row_list, columns=row_columns)
    df_jira["description"] = ""

    df_jira = df_jira.loc[df_jira["start_time"] > dt_cutoff]

    df_jira["day"] = df_jira["start_time"].apply(get_day)
    df_jira["end_time"] = df_jira["start_time"] + df_jira["duration"]

    df_hamster["source"] = "hamster"
    df_jira["source"] = "jira"

    df_all = pd.concat((df_hamster, df_jira), ignore_index=True)
    if args.first_day:
        print("Removing worklogs from time before ", args.first_day)
        df_all.drop(
            df_all.loc[df_all["day"] < args.first_day].index,
            inplace=True,
        )

    df_all.sort_values(["day", "start_time"], inplace=True)

    # Improvement : add assigned issues to hamster db as activities
    # issues = jira.search_issues(f"assignee={user_id}", maxResults=False)
    # for issue in issues:
    #     print(issue.key, issue.get_field("summary"))

    for day in sorted(df_all["day"].unique()):
        df = df_all.loc[df_all["day"] == day]
        pi_list = sorted(
            set(
                df.apply(
                    lambda row: (
                        row["project"] if not pd.isna(row["project"]) else "__NA__",
                        row["issue_number"],
                    ),
                    axis="columns",
                )
            )
        )

        days_worklogs_with_no_projects = []
        for project, issue_number in pi_list:
            if args.verbose:
                print(f"Updating worklogs for {project}-{issue_number}")
            if project == "__NA__":
                print(f"FOUND WORKLOG WITH NO PROJECT ASSIGNED: day = ", day)
                days_worklogs_with_no_projects.append(day)
                continue
            t = update_jira_worklog(
                jira=jira,
                day=pd.to_datetime(day),
                project=project,
                issue_number=issue_number,
                df_all=df_all,
                verbose=args.verbose,
                dry_run=args.dry_run,
            )

    w = pd.isna(df_all["project"])
    df = df_all.loc[w]
    if len(df) > 0:
        print("\n" * 5)
        print(f"ATTENTION: {len(df)} WORKLOG ITEMS HAS NO PROJECT ASSIGNED:")
        print(df)
    else:
        print("It seems like we could match worklogs to projects everywhere")
    if len(days_worklogs_with_no_projects):
        print("!!! ON SOME DAYS THERE ARE WORKLOGS WITH NO PROJECTS ASSIGNED !!!")
        print(days_worklogs_with_no_projects)

    print("Synchronization of worklogs since ", dt_cutoff, " is finished")
