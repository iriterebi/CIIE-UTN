#!/bin/bash

SESSION="ros_agent_session"

tmux new-session -d -s $SESSION

tmux rename-window -t $SESSION:0 "InOrbit"
tmux send-keys -t $SESSION:0 "/root/.inorbit/dist/inorbit_ros" Enter

tmux attach-session -t $SESSION