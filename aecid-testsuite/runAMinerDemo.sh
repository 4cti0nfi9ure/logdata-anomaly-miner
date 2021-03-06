if [[ $1 == *.py ]]; then
    cp $1 /tmp/demo-config.py
    sudo chown aminer:aminer /tmp/demo-config.py 2> /dev/null
elif [[ $1 == *.yml ]]; then
    cp $1 /tmp/demo-config.yml
    sudo chown aminer:aminer /tmp/demo-config.yml 2> /dev/null
else
    exit 2
fi
sudo chown -R aminer:aminer /tmp/lib 2> /dev/null
sudo chmod +x demo/AMiner/aminerDemo.sh
sudo ./demo/AMiner/aminerDemo.sh > /tmp/demo
exit_code=$?
sudo rm /tmp/demo-config.py
sudo rm /tmp/demo
sudo rm /tmp/syslog
sudo rm /tmp/AMinerRemoteLog.txt
exit $exit_code
