import styles from "./App.module.css";

function App() {
  return (
    <main className={styles.appShell}>
      <section className={styles.heroCard}>
        <h1>ZUS AI Assistant</h1>
        <p>
          Frontend scaffold in place. Implement chat interface, planner timeline, and unhappy-flow
          indicators here.
        </p>
      </section>
    </main>
  );
}

export default App;
