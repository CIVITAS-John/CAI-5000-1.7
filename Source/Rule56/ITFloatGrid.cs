using System.Runtime.CompilerServices;
using Verse;
namespace CombatAI
{
    public class ITFloatGrid
    {
        public const int BLOCK_SIZE = 16;

        private readonly CellIndices cellIndices;
        private readonly ITCell[]    grid;
        // Last cycle each BLOCK_SIZE square was written, so readers can tell when a
        // whole block reads as 0 without scanning it.
        private readonly ushort[]    blockCycle;
        private readonly int         mapSizeX, blocksX, blocksZ;

        public readonly int    mapCellNum;
        private         ushort cycleNum = 19;

        private ushort sig = 13;

        public ITFloatGrid(Map map)
        {
            cellIndices = map.cellIndices;
            grid        = new ITCell[cellIndices.NumGridCells];
            mapCellNum  = cellIndices.NumGridCells;
            mapSizeX    = map.Size.x;
            blocksX     = (mapSizeX + BLOCK_SIZE - 1) / BLOCK_SIZE;
            blocksZ     = (map.Size.z + BLOCK_SIZE - 1) / BLOCK_SIZE;
            blockCycle  = new ushort[blocksX * blocksZ];
            for (int i = 0; i < blockCycle.Length; i++)
            {
                blockCycle[i] = (ushort)(cycleNum - 2);
            }
        }

        public int CycleNum
        {
            get => cycleNum;
        }

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public void Set(IntVec3 cell, float value)
        {
            Set(cellIndices.CellToIndex(cell), value);
        }
        public void Set(int index, float value)
        {
            if (index >= 0 && index < mapCellNum)
            {
                int z = index / mapSizeX;
                blockCycle[z / BLOCK_SIZE * blocksX + (index - z * mapSizeX) / BLOCK_SIZE] = cycleNum;
                ITCell cell = grid[index];
                if (cell.sig != sig)
                {
                    int dc = cycleNum - cell.cycleNum;
                    if (dc == 0)
                    {
                        cell.value += value;
                    }
                    else
                    {
                        if (dc == 1)
                        {
                            cell.valuePrev = cell.value;
                        }
                        else
                        {
                            cell.valuePrev = 0;
                        }
                        cell.cycleNum = cycleNum;
                        cell.value    = value;
                    }
                    cell.sig    = sig;
                    grid[index] = cell;
                }
            }
        }

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public float Get(IntVec3 cell)
        {
            return Get(cellIndices.CellToIndex(cell));
        }
        public float Get(int index)
        {
            if (index >= 0 && index < mapCellNum)
            {
                ITCell cell = grid[index];
                int    dc   = cycleNum - cell.cycleNum;
                switch (dc)
                {
                    case 0:
                        return Maths.Max(cell.value, cell.valuePrev);
                    case 1:
                        return cell.value;
                    default:
                        return 0;
                }
            }
            return 0;
        }

        /// <summary>
        ///     Whether every cell in block (<paramref name="bx" />, <paramref name="bz" />) reads as 0: Get only returns
        ///     values written this cycle or the previous one. Blocks outside the map are cold.
        /// </summary>
        public bool IsBlockCold(int bx, int bz)
        {
            if ((uint)bx >= (uint)blocksX || (uint)bz >= (uint)blocksZ)
            {
                return true;
            }
            return (ushort)(cycleNum - blockCycle[bz * blocksX + bx]) >= 2;
        }

        public void Next()
        {
            if (sig++ == short.MaxValue)
            {
                sig = 13;
            }
        }

        public void NextCycle()
        {
            Next();
            if (cycleNum++ == short.MaxValue)
            {
                sig = 13;
            }
        }

        private struct ITCell
        {
            public float  value;
            public float  valuePrev;
            public ushort sig;
            public ushort cycleNum;
        }
    }
}
