#!/bin/bash

SESSION="ros_agent_session"

tmux new-session -d -s $SESSION

tmux rename-window -t $SESSION:0 "InOrbit"
tmux send-keys -t $SESSION:0 "source /opt/ros/humble/setup.bash && /root/.inorbit/dist/scripts/start.sh 2>&1 | tee /tmp/inorbit.log" Enter

# Second window: Arduino scrapper
tmux new-window -t $SESSION:1 -n "Arduino Scrapper"
tmux send-keys -t $SESSION:1 "source /opt/ros/humble/setup.bash && cd agent/serial_scraper/ && python3 scraper.py" Enter

# Third window: Listener
tmux new-window -t $SESSION:2 -n "Agent Listener"
tmux send-keys -t $SESSION:2 "source /opt/ros/humble/setup.bash && cd agent/ && python3 listener.py" Enter


# Fourth window: Camera node
tmux new-window -t $SESSION:3 -n "Camera"
tmux send-keys -t $SESSION:3 "source /opt/ros/humble/setup.bash && cd agent/camera/ && python3 camera_node.py" Enter

# Fifth window: interactive terminal
tmux new-window -t $SESSION:4 -n "Terminal"

tmux attach-session -t $SESSION -t $SESSION:1
