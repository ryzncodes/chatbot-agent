describe("Rate limit handling", () => {
  it("shows a friendly retry message and disables send on 429", () => {
    cy.intercept("POST", "**/chat", (req) => {
      req.reply({
        statusCode: 429,
        headers: {
          "Retry-After": "3",
          "X-RateLimit-Limit": "10",
          "X-RateLimit-Remaining": "0",
          "X-RateLimit-Reset": `${Math.floor(Date.now() / 1000) + 3}`,
        },
        body: {
          error: "rate_limit_exceeded",
          message: "Too many requests. Please retry later.",
          retry_after_seconds: 3,
        },
      });
    }).as("chat429");

    cy.visit("/");
    cy.get('textarea[placeholder="Type your message..."]').type("hello{enter}");
    cy.wait("@chat429");
    cy.contains("Too many requests").should("exist");
    cy.get("button[type=submit]").should("be.disabled");
  });
});

