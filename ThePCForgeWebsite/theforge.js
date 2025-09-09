// Define the parseBuildResponse function
function parseBuildResponse(response) {
  console.log("Response received:", response); // Debugging log

  // Dictionary of components (no specs field)
  const componentIds = {
    "Processor (CPU)": { model: "model-cpu", price: "price-cpu" },
    "Graphics Card (GPU)": { model: "model-gpu", price: "price-gpu" },
    "Motherboard": { model: "model-motherboard", price: "price-motherboard" },
    "Memory (RAM)": { model: "model-ram", price: "price-ram" },
    "Storage": { model: "model-storage", price: "price-storage" },
    "Power Supply (PSU)": { model: "model-psu", price: "price-psu" },
    "Case": { model: "model-case", price: "price-case" },
    "Cooling": { model: "model-cooling", price: "price-cooling" },
  };

  // 1) Clear existing fields so old values don’t persist
  Object.values(componentIds).forEach(({ model, price }) => {
    document.getElementById(model).value = "";
    document.getElementById(price).value = "";
  });

  // 2) Split new response into lines
  const lines = response.split("\n").filter((line) => line.trim() !== "");

  let currentComponent = null;

  lines.forEach((line) => {
    line = line.trim();

    // Check if line matches a component name
    if (componentIds[line]) {
      currentComponent = line;
      console.log(`Found component: ${currentComponent}`);
    } else if (currentComponent) {
      const { model, price } = componentIds[currentComponent];

      // Example line format: "- AMD Ryzen 5 7600 - £250"
      const detailsMatch = line.match(/^- (.+?) - £([\d,]+)/);
      if (detailsMatch) {
        const modelText = detailsMatch[1].trim();
        const priceText = `£${detailsMatch[2].trim()}`;

        // Populate only model & price
        document.getElementById(model).value = modelText;
        document.getElementById(price).value = priceText;

        console.log(
          `Updated fields for ${currentComponent}: Model: ${modelText}, Price: ${priceText}`
        );
      } else {
        console.warn(`Could not parse details for ${currentComponent}: ${line}`);
      }

      // Reset after processing the detail line
      currentComponent = null;
    } else {
      // Unrecognized line
      console.warn(`Line does not match any component or details: ${line}`);
    }
  });
}

// Event listener for the Send button
document.getElementById("send-button").addEventListener("click", async () => {
  const inputBox = document.getElementById("user-input");
  const query = inputBox.value;
  const outputBox = document.getElementById("chat-output");

  if (!query) {
    outputBox.innerHTML += `<p class='chat-message'>Please enter a valid question.</p>`;
    return;
  }

  // Show loading state on the button
  const sendButton = document.getElementById("send-button");
  sendButton.innerText = "LOADING...";
  sendButton.disabled = true;

  try {
    const response = await fetch("http://192.168.0.235:8080/api/build-pc", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query: query }),
    });

    if (!response.ok) {
      throw new Error("Failed to fetch data from the server.");
    }

    const data = await response.json();
    const pcBuild = data.pc_build || "No PC build generated.";
    const requirements = data.filtered_requirements || "No filtered requirements.";

    // Append the response to the chat output area
    outputBox.innerHTML += `
      <div class='chat-message'>
        <strong>Filtered Requirements:</strong><br>${requirements}<br><br>
        <strong>PC Build:</strong><br>${pcBuild}
      </div>
    `;

    // Parse PC Build data to fill the table
    console.log("Parsing PC Build data...");
    parseBuildResponse(pcBuild);
  } catch (error) {
    console.error("Error occurred:", error);
    outputBox.innerHTML += `<p class='chat-message'>An error occurred while fetching data.</p>`;
  } finally {
    sendButton.innerText = "Send";
    sendButton.disabled = false;
  }
});
