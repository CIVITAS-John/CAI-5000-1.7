using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using Verse;
namespace CombatAI
{
    public class AsyncActions
    {
        private static readonly List<AsyncActions> running = new List<AsyncActions>();
        private static           int               _globalInstanceCounter = 0;

        private readonly int hashOffset;

        public readonly  object locker_Main    = new object();
        public readonly  object locker_offMain = new object();
        private readonly int    mainLoopTickInterval;

        private readonly Queue<Action>  queuedMainThreadActions = new Queue<Action>();
        private readonly Queue<Action>  queuedOffThreadActions  = new Queue<Action>();
        private readonly AutoResetEvent waitHandle              = new AutoResetEvent(false);
        private readonly Thread         thread;
        private volatile bool           mainThreadActionQueueEmpty;
        private volatile bool           alive = true;
        private          bool           started;

        public AsyncActions(int mainLoopTickInterval = 5)
        {
            this.mainLoopTickInterval = mainLoopTickInterval;
            hashOffset                = System.Threading.Interlocked.Increment(ref _globalInstanceCounter) % 128;
            thread                    = new Thread(OffMainThreadActionLoop) { IsBackground = true };
        }

        public bool Alive => alive;

        public void Start()
        {
            lock (locker_offMain)
            {
                if (!alive || started) return;
                lock (running)
                {
                    thread.Start();
                    started = true;
                    running.Add(this);
                }
            }
        }

        public void ExecuteMainThreadActions()
        {
            MainThreadActionLoop();
        }

        public void Kill()
        {
            bool join;
            lock (locker_offMain)
            {
                if (!alive) return;
                alive = false;
                queuedOffThreadActions.Clear();
                // The worker owns disposal once started. Signal while holding the same lock
                // used by enqueue/disposal so nobody can signal a disposed wait handle.
                if (started) waitHandle.Set();
                else waitHandle.Dispose();
                join = started && Thread.CurrentThread != thread;
            }
            lock (locker_Main)
            {
                queuedMainThreadActions.Clear();
                mainThreadActionQueueEmpty = true;
            }
            lock (running)
            {
                running.Remove(this);
            }
            // Long-running callbacks must observe Alive and return cooperatively.
            if (join) thread.Join(100);
        }

        public static void KillAll()
        {
            List<AsyncActions> snapshot;
            lock (running)
            {
                snapshot = running.ToList();
            }
            foreach (AsyncActions asyncActions in snapshot)
            {
                asyncActions.Kill();
            }
        }

        public void EnqueueOffThreadAction(Action action)
        {
            lock (locker_offMain)
            {
                if (!alive) return;
                if (queuedOffThreadActions.Count > 1024)
                {
                    Log.Error($"ISMA: AsyncActions is leaking memory with more than {queuedOffThreadActions.Count} actions queued!");
                }
                else
                {
                    queuedOffThreadActions.Enqueue(action);
                    waitHandle.Set();
                }
            }
        }

        public void EnqueueMainThreadAction(Action action)
        {
            lock (locker_Main)
            {
                if (!alive) return;
                queuedMainThreadActions.Enqueue(action);
                mainThreadActionQueueEmpty = false;
            }
        }

        private Action DequeueOffThreadAction()
        {
            Action action = null;
            lock (locker_offMain)
            {
                if (alive && queuedOffThreadActions.Count > 0)
                {
                    action = queuedOffThreadActions.Dequeue();
                }
            }
            return action;
        }

        private Action DequeueMainThreadAction()
        {
            Action action = null;
            lock (locker_Main)
            {
                if (alive && queuedMainThreadActions.Count > 0)
                {
                    action = queuedMainThreadActions.Dequeue();
                }
                mainThreadActionQueueEmpty = queuedMainThreadActions.Count == 0;
            }
            return action;
        }

        private void MainThreadActionLoop()
        {
            if (!mainThreadActionQueueEmpty || (GenTicks.TicksGame + hashOffset) % mainLoopTickInterval == 0)
            {
                while (Alive)
                {
                    Action action = DequeueMainThreadAction();
                    if (action != null)
                    {
                        try
                        {
                            action();
                        }
                        catch (Exception er)
                        {
                            Log.Error(er.ToString());
                        }
                    }
                    else
                    {
                        break;
                    }
                }
            }
        }

        private void OffMainThreadActionLoop()
        {
            try
            {
                while (Alive)
                {
                    Action action = DequeueOffThreadAction();
                    if (action != null)
                    {
                        try
                        {
                            action();
                        }
                        catch (Exception er)
                        {
                            Log.Error(er.ToString());
                        }
                    }
                    else
                    {
                        waitHandle.WaitOne();
                    }
                }
            }
            finally
            {
                Kill();
                lock (locker_offMain)
                {
                    waitHandle.Dispose();
                }
            }
        }
    }
}
