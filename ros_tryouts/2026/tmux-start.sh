#!/bin/bash

SESSION="ros_agent_session"

tmux new-session -d -s $SESSION

tmux rename-window -t $SESSION:0 "InOrbit"
tmux send-keys -t $SESSION:0 "export ROS_DOMAIN_ID=42 && curl https://control.inorbit.ai/liftoff/WklSDRtViJNzWRPN | sh" Enter

tmux attach-session -t $SESSION