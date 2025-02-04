import torch
from torch.nn import functional as F
from modules.helpers import sequence_mask


def _kl_div(inp_logits, trg_logits, lengths, tau=1):
    """
    Compute the prior loss using a pretrained "oracle" LM.
    The loss is computed using the produced posteriors over the vocabulary
    produced by a generator and the posteriors of the "oracle" LM.

    Args:
        logits: the logits of the generator
        words: the argmax of the logits
        oracle: the oracle LM
        tau: the temperature of the softmax
        lengths: the lengths of the target sequence. Used for masking the loss.


    Debug = -F.softmax(_logits, -1) * torch.log(F.softmax(logits, -1) /
                                                F.softmax(_logits, -1))

    Returns:
        the average KL Divergence per timestep (word)

    """
    mask = sequence_mask(lengths).unsqueeze(-1).float()

    input_logp = F.log_softmax(inp_logits * mask / tau, -1)
    target_p = F.softmax(trg_logits * mask / tau, -1)

    # shape: batch x seq_length x tokens
    loss = F.kl_div(input_logp, target_p, reduction='none')

    # sum over words/vocab (KL per word/timestep !)
    # shape: batch x length
    loss = loss.sum(-1)

    # zero losses for padded timesteps
    loss = loss * mask.squeeze()

    total_loss = loss.sum() / mask.sum()

    return total_loss, loss


def _global_prior(logits, word_idx, lengths):
    """
    Evaluate the probability of a sequence, under a language model

    """

    mask = sequence_mask(lengths)
    labels = (word_idx * mask.long()).contiguous().view(-1)
    _logits = logits.contiguous().view(-1, logits.size(-1))
    loss = F.cross_entropy(_logits, labels, ignore_index=0, reduction='none')

    # normalize by length to avoid mode collapse
    total = loss.sum() / mask.float().sum()

    return total, loss.view(mask.size())


def kl_length(logits, lengths, eos):
    """
    Length control loss, using a sequence of length labels (with eos token).

    Args:
        logits:
        lengths:
        eos:

    Returns:

    """
    mask = sequence_mask(lengths - 1, lengths.max())
    eos_labels = ((~mask) * eos).long().contiguous().view(-1)

    _logits = logits.contiguous().view(-1, logits.size(-1))
    loss = F.cross_entropy(_logits, eos_labels, ignore_index=0)
    anti_loss = F.cross_entropy(_logits, eos_labels, ignore_index=2)

    return loss / (anti_loss + 1.0)


def pairwise_loss(a, b, dist="cosine"):
    if dist == "euclidean":
        return F.pairwise_distance(a, b).mean()
    elif dist == "cosine":
        return 1 - F.cosine_similarity(a, b).mean()
    elif dist == "dot":
        dot = torch.bmm(a.unsqueeze(1), b.unsqueeze(-1)).squeeze()
        scaled_dot = dot.mean() / a.size(1)
        return - scaled_dot
    elif dist == "cosine_max":
        return 1 - F.cosine_similarity(a, b, -1)
    elif dist == "euclidean_max":
        return F.pairwise_distance(a, b, -1)
    else:
        raise ValueError


def r(p, trj):
    batch = p.size(0)
    max_l = None
    max_len = trj.size(1)
    for i in range(max_len):
        p2 = trj[:, i, :]
        # 由于pairwise_loss对每个batch做了平均，所以返回的就是一个值

        l = pairwise_loss(p, p2, "cosine_max")
        # l中的值为1，说明两个向量恰好呈90，或者其中某个向量为0向量。后者发生的概率远大于前者，所以我们直接将1的值抹掉
        # l[torch.where(l == 1)] = 0
        # l[torch.where(l == 1.0000e-06)] = 0
        # assert torch.all(l != 1)
        if max_l == None:
            max_l = l
        else:
            # 将batch中的每一个更新，取最大值
            max_l = torch.max(max_l, l)
    return max_l.tolist()[0]



def energy_(region, inp, size_1):
    pass


def energy_2(region, inp, size_1, src_lengths):
    pass
