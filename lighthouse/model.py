from pony import orm
from datetime import datetime

db: orm.Database = orm.Database()


class Build(db.Entity):
    BUILD_TAG = orm.PrimaryKey(str, auto=False)

    BUILD_CAUSE = orm.Required(str)
    BUILD_ID = orm.Required(str)
    BUILD_URL = orm.Required(str)

    ghprbActualCommit = orm.Required(str)
    ghprbActualCommitAuthor = orm.Required(str)
    ghprbActualCommitAuthorEmail = orm.Required(str)
    ghprbPullDescription = orm.Required(str)
    ghprbPullLink = orm.Required(str)
    ghprbPullTitle = orm.Required(str)
    ghprbSourceBranch = orm.Required(str)
    ghprbTargetBranch = orm.Required(str)

    GIT_BRANCH = orm.Required(str)
    GIT_COMMIT = orm.Required(str)
    GIT_PREVIOUS_COMMIT = orm.Required(str)

    NODE_NAME = orm.Required(str)

    make_file = orm.Optional(str)

    checkpoints = orm.Set("CheckPoint")


class CheckPoint(db.Entity):
    BUILD_TAG = orm.Required(Build)
    datetime = orm.Required(datetime)
    start_or_finish = orm.Required(str)
    make_target_name = orm.Required(str)
    exit_code = orm.Optional(bool)


@orm.db_session
def create_build(environment_dict):
    filtered_env_dict = {
        key: environment_dict[key] for key in Build._columns_ if key in environment_dict
    }
    Build(**filtered_env_dict)


@orm.db_session
def report_checkpoint(tag, time, start_or_finish, make_target_name, exit_code=None):
    this_build = Build[tag]
    CheckPoint(
        BUILD_TAG=this_build,
        datetime=datetime.fromtimestamp(time),
        start_or_finish=start_or_finish,
        make_target_name=make_target_name,
        exit_code=exit_code,
    )


@orm.db_session
def get_build_dict(tag):
    return Build[tag].to_dict()


@orm.db_session
def get_checkpoint_by_build_and_target(build, target):
    if build == '*':
        filter_func = lambda item: item.make_target_name == target
    elif target == '*':
        filter_func = lambda item: item.BUILD_TAG == Build[build]
    else:
        filter_func = lambda item: item.BUILD_TAG == Build[build] and item.make_target_name == target
    checkpoints = CheckPoint.select(
        filter_func
    ).fetch()
    return list(c.to_dict() for c in checkpoints)


def init_db(filename=":memory:", debug=False):
    if debug:
        orm.set_sql_debug(True)

    db.bind(provider="sqlite", filename=filename, create_db=True)
    db.generate_mapping(create_tables=True)


def inject_test_data(path, tag):
    import json
    import time

    env = json.load(open(path))
    create_build(env)

    report_checkpoint(tag, time.time(), "start", "build_py36rpc")
    report_checkpoint(tag, time.time(), "finish", "build_py36rpc", exit_code=1)


if __name__ == "__main__":
    init_db(debug=True)

    # test case
    inject_test_data()

    tag = "jenkins-Clipper-PRB-1672"
    with orm.db_session():
        assert Build.select()[:][0] == Build[tag]

    with orm.db_session():
        assert Build[tag].checkpoints.count() == 2
