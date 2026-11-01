/**
 * @param {string[]} strs
 * @return {string[][]}
 */
var groupAnagrams = function(strs) {
    const groups = {};
    for (const s of strs) {
        const key = s.split('').sort().join('');
        (groups[key] ||= []).push(s);
    }
    return Object.values(groups);
};
