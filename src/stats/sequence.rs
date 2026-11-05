use std::{collections::HashMap, hash::Hash};

pub(crate) fn matching_blocks<T: Eq + Hash>(left: &[T], right: &[T]) -> Vec<(usize, usize, usize)> {
    let mut pos: HashMap<&T, Vec<usize>> = HashMap::new();
    for (idx, val) in right.iter().enumerate() {
        pos.entry(val).or_default().push(idx);
    }
    let mut pending: Vec<(usize, usize, usize, usize)> = vec![(0, left.len(), 0, right.len())];
    let mut res: Vec<(usize, usize, usize)> = Vec::new();
    while let Some((left_start, left_end, right_start, right_end)) = pending.pop() {
        let mut best: (usize, usize, usize) = (left_start, right_start, 0);
        let mut prev: HashMap<usize, usize> = HashMap::new();
        for (left_idx, val) in left.iter().enumerate().take(left_end).skip(left_start) {
            let mut cur: HashMap<usize, usize> = HashMap::new();
            for right_idx in pos
                .get(val)
                .into_iter()
                .flatten()
                .copied()
                .filter(|idx| *idx >= right_start && *idx < right_end)
            {
                let size: usize = right_idx
                    .checked_sub(1)
                    .and_then(|idx| prev.get(&idx).copied())
                    .unwrap_or(0)
                    + 1;
                cur.insert(right_idx, size);
                if size > best.2 {
                    best = (left_idx + 1 - size, right_idx + 1 - size, size);
                }
            }
            prev = cur;
        }
        if best.2 == 0 {
            continue;
        }
        res.push(best);
        if best.0 > left_start && best.1 > right_start {
            pending.push((left_start, best.0, right_start, best.1));
        }
        if best.0 + best.2 < left_end && best.1 + best.2 < right_end {
            pending.push((best.0 + best.2, left_end, best.1 + best.2, right_end));
        }
    }
    res.sort_unstable();
    let mut merged: Vec<(usize, usize, usize)> = Vec::new();
    for block in res {
        if let Some(last) = merged
            .last_mut()
            .filter(|last| last.0 + last.2 == block.0 && last.1 + last.2 == block.1)
        {
            last.2 += block.2;
        } else {
            merged.push(block);
        }
    }
    merged.push((left.len(), right.len(), 0));
    merged
}
