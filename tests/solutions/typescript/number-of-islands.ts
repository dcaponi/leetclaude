function numIslands(grid: string[][]): number {
    const rows = grid.length, cols = grid[0].length;
    const dirs: [number, number][] = [[1, 0], [-1, 0], [0, 1], [0, -1]];
    let islands = 0;
    for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
            if (grid[r][c] !== "1") continue;
            islands++;
            const queue: [number, number][] = [[r, c]];
            grid[r][c] = "0";
            while (queue.length) {
                const [x, y] = queue.shift()!;
                for (const [dx, dy] of dirs) {
                    const nx = x + dx, ny = y + dy;
                    if (nx >= 0 && ny >= 0 && nx < rows && ny < cols && grid[nx][ny] === "1") {
                        grid[nx][ny] = "0";
                        queue.push([nx, ny]);
                    }
                }
            }
        }
    }
    return islands;
};
