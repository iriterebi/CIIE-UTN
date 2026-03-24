#!/bin/bash

SESSION="ros_agent_session"

tmux new-session -d -s $SESSION

tmux rename-window -t $SESSION:0 "InOrbit"
tmux send-keys -t $SESSION:0 "source /opt/ros/humble/setup.bash && /root/.inorbit/dist/scripts/start.sh 2>&1 | tee /tmp/inorbit.log" Enter

# Second window: Arduino scrapper
tmux new-window -t $SESSION:1 -n "Arduino Scrapper"
tmux send-keys -t $SESSION:1 "cd agent/serial_scraper/ && python3 scraper.py" Enter

# Third window: interactive terminal, prints banner when InOrbit connects
tmux new-window -t $SESSION:2 -n "Terminal"

tmux attach-session -t $SESSION -t $SESSION:1
