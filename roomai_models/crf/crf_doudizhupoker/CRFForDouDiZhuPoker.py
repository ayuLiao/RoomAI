#!/bin/python
import random

from roomai_models.crf.algorithms import CRFPlayer
import roomai.doudizhupoker
import numpy as np

pattern_to_idx = dict()
patterns_list  = list(roomai.doudizhupoker.AllPatterns.keys())
patterns_list.sort()
for p in patterns_list:
    pattern_to_idx[p] = len(pattern_to_idx)

card_to_idx = dict()
for i in range(3,10):
    card_to_idx[str(i)] = i - 3
card_to_idx["T"] = len(card_to_idx)
card_to_idx["J"] = len(card_to_idx)
card_to_idx["Q"] = len(card_to_idx)
card_to_idx["K"] = len(card_to_idx)
card_to_idx["A"] = len(card_to_idx)
card_to_idx["2"] = len(card_to_idx)
card_to_idx["r"] = len(card_to_idx)
card_to_idx['R'] = len(card_to_idx)

num_pattern  = len(roomai.doudizhupoker.AllPatterns)
num_card     = 15

all_action_feats = dict()


env_for_available_actions  = roomai.doudizhupoker.DouDiZhuPokerEnv()
env_for_available_actions .init({"param_start_turn": 0})
env_for_available_actions .forward(roomai.doudizhupoker.DouDiZhuPokerAction.lookup("b"))
env_for_available_actions .forward(roomai.doudizhupoker.DouDiZhuPokerAction.lookup("x"))
infos_for_available_actions, public_state_for_available_actions, person_states_for_available_actions, private_state_for_available_actions =\
    env_for_available_actions .forward(roomai.doudizhupoker.DouDiZhuPokerAction.lookup("x"))


def available_actions(hand_cards_str, last_action_str):
    if last_action_str == "x":
        person_states_for_available_actions[0].__hand_cards__ = roomai.doudizhupoker.DouDiZhuPokerHandCards(hand_cards_str)
        return env_for_available_actions.available_actions(env_for_available_actions.public_state, env_for_available_actions.person_states[0])
    else:
        person_states_for_available_actions[0].__hand_cards__ = roomai.doudizhupoker.DouDiZhuPokerHandCards(hand_cards_str + last_action)
        person_states_for_available_actions[1].__hand_cards__ = roomai.doudizhupoker.DouDiZhuPokerHandCards(hand_cards_str)
        infos, public_state, person_states, private_state = env_for_available_actions.forward(roomai.doudizhupoker.DouDiZhuPokerAction.lookup(last_action))
        return person_states[1].available_actions

def next_hand_cards(hand_cards_str, action_str):
    roomai.doudizhupoker.DouDiZhuPokerHandCards(hand_cards_str).__remove_action__(action_str)
    return "x"

class CRFForDouDiZhuPokerPlayer(CRFPlayer):
    ### different feature ####
    def gen_info_feat(self, info):
        struct_feat = np.zeros((num_pattern, num_card))
        for action in info.person_state.available_actions:
            row_id = pattern_to_idx[action.pattern[0]]
            col_id = action.maxMasterPoint
            struct_feat[row_id, col_id] += 1.0
        return struct_feat

    def gen_action_feat(self, action):
        if action.key in all_action_feats:
            return all_action_feats[action.key]
        else:
            struct_feat = np.zeros((num_pattern, num_card))
            row_id = pattern_to_idx[action.pattern[0]]
            col_id = action.maxMasterPoint
            struct_feat[row_id, col_id] += 1.0
            all_action_feats[action.key] = struct_feat
            return all_action_feats[action.key]

    def gen_actions_feat(self, actions):
        struct_feat = np.zeros((num_pattern, num_card))
        for action in actions:
            struct_feat += self.gen_action_feat(action)
        return struct_feat

    def gen_info_action_feat(self, info, action):
        next_hand_cards_str = next_hand_cards(info.person_state.hand_cards.key)
        np.hstack([self.gen_info_feat(info).reshape((num_pattern * num_card)), \
                   self.gen_action_feat(action).reshape((num_pattern * num_card)), \
                   self.gen_actions_feat(available_actions(next_hand_cards_str,"x")).reshape((num_pattern * num_card))])

    def gen_info_actions_feat(self, info, actions):
        x                        = np.zeros((len(actions), num_pattern, num_card, 6))
        current_info_feat        = self.gen_info_feat(info)
        history_action_feats     = [np.zeros((num_pattern, num_card)) for i in range(3)]

        for idx_action in range(info.public_state.action_history):
            idx             = idx_action[0]
            currrent_idx    = info.person_state.id
            action          = idx_action[1]
            history_action_feats[(idx + 3 -currrent_idx) % 3] += self.gen_action_feat(action)

        for i in range(len(actions)):
            act = actions[i]
            act_feat = self.gen_action_feat(act)

            next_hand_cards_str  = next_hand_cards(info.person_state.hand_cards.key)
            next_hand_cards_feat = self.gen_actions_feat(available_actions(next_hand_cards_str, "x"))

            x[i, :, :, 0] = current_info_feat
            x[i, :, :, 1] = history_action_feats[0]
            x[i, :, :, 2] = history_action_feats[1]
            x[i, :, :, 3] = history_action_feats[2]
            x[i, :, :, 4] = act_feat
            x[i, :, :, 5] = next_hand_cards_feat

        return x

    def receive_info(self, info):
        self.state             = self.gen_state(info)
        self.available_actions = info.person_state.available_actions.values()

    def take_action(self):
        probs = self.get_strategies(self.state, self.available_actions)
        sum1  = sum(probs)
        for i in range(len(self.available_actions)):
            probs[i] /= sum

        r    = random.random()
        sum1 = 0
        for i in range(len(probs)):
            sum1 += probs[i]
            if sum1 > r:
                return self.available_actions[i]

        return self.available_actions[len(self.available_actions)-1]


    def reset(self):
        pass

'''
example usage:
if __name__ == "__main__":
    env     = KuhnPokerEnv()
    player  = KuhnPokerCRMPlayer()
    import roomai_models.crf.algorithms
    algo    = roomai_models.crf.algorithms.CRFOutSampling
    for i in range(10000):
        algo.dfs(env = env, player=player, p0 = 1, p1 = 1, deep = 0)

    print (player.regrets)
    print (player.strategies)
    player.is_train = False

    import roomai.common
    player_random = roomai.common.RandomPlayer()
    sum_scores = [0.0,0.0]
    num        = 0
    for i in range(10000):
        scores = KuhnPokerEnv.compete(env,[player, player_random])
        sum_scores[0] += scores[0]
        sum_scores[1] += scores[1]
        num           += 1
    for i in range(len(sum_scores)):
        sum_scores[i] /= num
    print (sum_scores)


    player_alwaysbet = Example_KuhnPokerAlwaysBetPlayer()
    sum_scores = [0.0,0.0]
    num        = 0
    for i in range(10000):
        scores = KuhnPokerEnv.compete(env,[player, player_alwaysbet])
        sum_scores[0] += scores[0]
        sum_scores[1] += scores[1]
        num           += 1
    for i in range(len(sum_scores)):
        sum_scores[i] /= num
    print (sum_scores)

    sum_scores = [0.0, 0.0]
    num = 0
    for i in range(10000):
        scores = KuhnPokerEnv.compete(env, [player_random, player_alwaysbet])
        sum_scores[0] += scores[0]
        sum_scores[1] += scores[1]
        num += 1
    for i in range(len(sum_scores)):
        sum_scores[i] /= num
    print (sum_scores)

'''
