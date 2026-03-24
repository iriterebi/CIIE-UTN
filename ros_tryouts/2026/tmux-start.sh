#!/bin/bash

SESSION="ros_agent_session"

tmux new-session -d -s $SESSION

tmux rename-window -t $SESSION:0 "InOrbit"
tmux send-keys -t $SESSION:0 "source /opt/ros/humble/setup.bash && /root/.inorbit/dist/scripts/start.sh 2>&1 | tee /tmp/inorbit.log" Enter

# Second window: interactive terminal, prints banner when InOrbit connects
tmux new-window -t $SESSION:1 -n "Terminal"
tmux send-keys -t $SESSION:1 "tail -f /tmp/inorbit.log | grep -m1 'Connected to MQTT' && echo '' && echo '=====================================' && echo '  Robot connected to InOrbit!' && echo '=====================================' && exec bash" Enter

tmux attach-session -t $SESSION -t $SESSION:1
