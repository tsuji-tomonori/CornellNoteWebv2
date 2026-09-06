import { createRoot } from "react-dom/client";
import { App } from "./App";
import { completeLogin } from "./auth";
import "./style.css";
completeLogin()
  .then(() => createRoot(document.getElementById("root")!).render(<App />))
  .catch((e: Error) =>
    createRoot(document.getElementById("root")!).render(
      <App initialError={e.message} />,
    ),
  );
