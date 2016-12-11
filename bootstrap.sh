#!/bin/bash

USER=$(whoami)
FORCE_CLEAN="false"
START_WORKER="false"
SUDO_CMD="sudo -u $USER "

function clean_server()
{
    # Reset environment and db
    $SUDO_CMD python ./manage.py sqlflush | python ./manage.py dbshell

    rm -rf celerybeat-schedule db.sqlite3
}

function setup_server()
{
    touch celery_worker.log

    chown $USER caselink/backups celery_worker.log

    # Start initial database
    $SUDO_CMD python ./manage.py migrate

    $SUDO_CMD python ./manage.py loaddata caselink/fixtures/initial_data.yaml

    if [ -f caselink/fixtures/latest.yaml ]; then
        $SUDO_CMD python ./manage.py loaddata caselink/fixtures/latest.yaml
    else
        $SUDO_CMD python ./manage.py loaddata caselink/fixtures/baseline.yaml
    fi

    $SUDO_CMD python ./manage.py manualinit
}


function run_celery(){
    #TODO use a better way to stop celery workers.
    pkill -f celery

    sudo systemctl restart rabbitmq-server

    # Start celery worker
    $SUDO_CMD celery worker -A caselink -n localhost -l info -f celery_worker.log --purge --detach
}


function start_server()
{
    $SUDO_CMD python ./manage.py migrate

    $SUDO_CMD python ./manage.py loaddata caselink/fixtures/initial_data.yaml

    # Run server
    $SUDO_CMD python ./manage.py runserver 0.0.0.0:8888
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
    run_celery
fi

start_server
