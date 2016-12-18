#!/bin/bash

USER=$(whoami)
FORCE_CLEAN="false"
START_WORKER="false"
SUDO_CMD="sudo -E -u $USER "
PYTHON=$(which python)

function clean_server()
{
    # Reset environment and db
    $SUDO_CMD $PYTHON ./manage.py sqlflush | $PYTHON ./manage.py dbshell

    rm -rf celerybeat-schedule db.sqlite3
}

function setup_server()
{
    touch celery_worker.log

    chown $USER caselink/backups celery_worker.log

    # Start initial database
    $SUDO_CMD $PYTHON ./manage.py migrate

    $SUDO_CMD $PYTHON ./manage.py loaddata caselink/fixtures/initial_data.yaml

    if [ -f caselink/fixtures/latest.yaml ]; then
        $SUDO_CMD $PYTHON ./manage.py loaddata caselink/fixtures/latest.yaml
    else
        $SUDO_CMD $PYTHON ./manage.py loaddata caselink/fixtures/baseline.yaml
    fi

    $SUDO_CMD $PYTHON ./manage.py manualinit
}


function rerun_celery(){
    #TODO use a better way to stop celery workers.
    pkill -f celery

    echo "Rnning celery worker, logging in celery_worker.log"
    $SUDO_CMD $PYTHON -m celery worker -A caselink -n localhost -l info -f celery_worker.log --purge --detach
}


function start_server()
{
    $SUDO_CMD $PYTHON ./manage.py migrate

    $SUDO_CMD $PYTHON ./manage.py loaddata caselink/fixtures/initial_data.yaml

    # Run server
    $SUDO_CMD $PYTHON ./manage.py runserver 0.0.0.0:8888
}


while [ "$1" != "" ]; do
    case $1 in
        --clean )
            FORCE_CLEAN="true"
            ;;
        --worker )
            START_WORKER="true"
            ;;
        --safe )
            USER=nobody
            ;;
        * )
            echo "
            Usage:
                --clean: Clean up database and enviroment
            "
            exit 1
    esac
    shift
done

if [[ "$FORCE_CLEAN" == "true" ]]; then
    clean_server
    setup_server
fi

if [[ "$START_WORKER" == "true" ]]; then
    rerun_celery
fi

start_server
