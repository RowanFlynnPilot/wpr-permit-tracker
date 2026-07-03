import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "leaflet/dist/leaflet.css";
import "./app.css";

createRoot(document.getElementById("root")).render(<App />);
