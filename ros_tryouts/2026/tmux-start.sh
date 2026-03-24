#!/bin/bash

SESSION="ros_agent_session"

tmux new-session -d -s $SESSION

tmux rename-window -t $SESSION:0 "InOrbit"
tmux send-keys -t $SESSION:0 "source /opt/ros/humble/setup.bash && /root/.inorbit/dist/scripts/start.sh" Enter

tmux attach-session -t $SESSION
