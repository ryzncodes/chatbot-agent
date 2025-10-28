describe("Chat flow", () => {
  beforeEach(() => {
    cy.intercept("POST", "**/chat", { fixture: "chat-success.json" }).as("chat");
    cy.visit("/");
  });

  it("sends a message and renders assistant response", () => {
    cy.get('textarea[placeholder="Type your message..."]').type("/calc 1 + 2{enter}");
    cy.wait("@chat");
    cy.contains("Assistant").should("exist");
    cy.contains("2").should("exist");
  });
});
