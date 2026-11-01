// Definition for singly-linked list.
// #[derive(PartialEq, Eq, Clone, Debug)]
// pub struct ListNode {
//   pub val: i32,
//   pub next: Option<Box<ListNode>>
// }
use std::cmp::Ordering;
use std::collections::BinaryHeap;

// Min-heap order on the node value.
impl PartialOrd for ListNode {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for ListNode {
    fn cmp(&self, other: &Self) -> Ordering {
        other.val.cmp(&self.val)
    }
}

impl Solution {
    pub fn merge_k_lists(lists: Vec<Option<Box<ListNode>>>) -> Option<Box<ListNode>> {
        let mut heap: BinaryHeap<Box<ListNode>> = lists.into_iter().flatten().collect();
        let mut dummy = Box::new(ListNode::new(0));
        let mut tail = &mut dummy;
        while let Some(mut node) = heap.pop() {
            if let Some(next) = node.next.take() {
                heap.push(next);
            }
            tail.next = Some(node);
            tail = tail.next.as_mut().unwrap();
        }
        dummy.next
    }
}
