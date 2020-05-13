import grpc

import envData_pb2
import envData_pb2_grpc

import time
import random
from DQN import DQN
import torch

SLEEP_TIME = 3

def run_DQN():

    MAXSTEP = 50

    with grpc.insecure_channel('localhost:50051') as channel:
        
        stub = envData_pb2_grpc.SimulatorStub(channel)
        dqn = DQN(observation_dim=12, action_dim=4, memory_capacity=40)

        # send action control command and get the response
        for i_episode in range(1000):
            obs = stub.getObservation(envData_pb2.AgentIndex(idx=0))
            obs_value = obs.ObservationValue
            # fill the 110,0000,0000(11 bit) to 0110,0000,0000(12 bit), bucause our observation's dimention is 12  
            obs_info_list = bin(obs_value)[2:].rjust(12, '0')
            obs_list = [int(info) for info in obs_info_list]
            obs_list = torch.FloatTensor(obs_list)
            running_loss = 0
            cumulative_reward = 0
            step = 0

            while True:
                time.sleep(SLEEP_TIME)
                step += 1
                stub.render(envData_pb2.UpdateCommand())
                action = dqn.choose_action(obs_list)

                StepResult = stub.step(envData_pb2.StepCommand(action_idx=action))
                r = StepResult.reward
                done = StepResult.terminal

                obs_ = stub.getObservation(envData_pb2.AgentIndex(idx=0))
                # fill the 110,0000,0000(11 bit) to 0110,0000,0000(12 bit), bucause our observation's dimention is 12  
                obs_info_list_ = bin(obs_.ObservationValue)[2:].rjust(12, '0')
                obs_list_ = [int(info) for info in obs_info_list_]
                obs_list_ = torch.FloatTensor(obs_list_)

                dqn.store_transition(obs_list, action, r, obs_list_)

                cumulative_reward += r
                if dqn.point > dqn.memory_capacity:
                    loss = dqn.learn()
                    running_loss += loss
                    if done or step > MAXSTEP:
                        print("\n[INFO] Episode: %d Cumulative Reward: %.2f\n" % (i_episode, cumulative_reward))
                        stub.reset(envData_pb2.ResetCommand())
                        break
                    elif step % 5 == 4:
                        print("Episode: %d| Global Step: %d| Loss:  %.4f, Reward: %.2f, Exploration: %.4f" % (i_episode, dqn.learn_step, running_loss / step, cumulative_reward, dqn.epsilon))
                else:
                    print("\rCollecting experience: %d / %d..." % (dqn.point, dqn.memory_capacity), end='')

                if done:
                    stub.reset(envData_pb2.ResetCommand())
                    break
                obs_list = torch.FloatTensor(obs_list_)

def run():
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = envData_pb2_grpc.SimulatorStub(channel)

        obs = stub.getObservation(envData_pb2.AgentIndex(idx=0))
        stub.render(envData_pb2.UpdateCommand())
        print("{\n\tInitial Agent Position: (%d, %d)\n}" % (obs.AgentPosX, obs.AgentPosY))
        time.sleep(SLEEP_TIME)

        # send action control command and get the response
        for _ in range(5):
            obs = stub.getObservation(envData_pb2.AgentIndex(idx=0))

            # action_idx = random.randint(0, 3)
            action_idx = 1
            StepResult = stub.step(envData_pb2.StepCommand(action_idx=action_idx))

            stub.render(envData_pb2.UpdateCommand())

            obs_value = obs.ObservationValue
            # fill the 110,0000,0000(11 bit) to 0110,0000,0000(12 bit), bucause our observation's dimention is 12  
            obs_info_list = bin(obs_value)[2:].rjust(12, '0')

            print("{\n\tAgent Position: (%d, %d)\n\tObservation Value: %d\n\tObservation Info: %s\n\tChoose Action: %d\n\tReward: %f\n}" % (obs.AgentPosX, obs.AgentPosY, obs.ObservationValue, obs_info_list, action_idx, StepResult.reward))
            
            if StepResult.terminal:
                stub.reset(envData_pb2.ResetCommand())
                stub.render(envData_pb2.UpdateCommand())

            time.sleep(SLEEP_TIME)


if __name__ == "__main__":
    run()
    # run_DQN()
