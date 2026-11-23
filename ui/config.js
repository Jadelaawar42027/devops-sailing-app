// Where the two services live. This file is overwritten by the CD pipeline with the
// Azure Container Apps URLs (see .github/workflows/cd.yml). Local values match docker-compose.
window.APP_CONFIG = {
  apiUrl: "http://localhost:8010",
  forecastUrl: "http://localhost:8011",
};
