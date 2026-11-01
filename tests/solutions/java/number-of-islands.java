class Solution {
    private static final int[][] DIRS = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};

    public int numIslands(char[][] grid) {
        int m = grid.length, n = grid[0].length, count = 0;
        for (int i = 0; i < m; i++) {
            for (int j = 0; j < n; j++) {
                if (grid[i][j] != '1') continue;
                count++;
                Deque<int[]> queue = new ArrayDeque<>();
                queue.offer(new int[] {i, j});
                grid[i][j] = '0';
                while (!queue.isEmpty()) {
                    int[] cur = queue.poll();
                    for (int[] d : DIRS) {
                        int x = cur[0] + d[0], y = cur[1] + d[1];
                        if (x >= 0 && y >= 0 && x < m && y < n && grid[x][y] == '1') {
                            grid[x][y] = '0';
                            queue.offer(new int[] {x, y});
                        }
                    }
                }
            }
        }
        return count;
    }
}
