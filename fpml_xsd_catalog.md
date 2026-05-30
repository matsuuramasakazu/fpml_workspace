The schema files are labelled fpml-XXX-MajorVersion-MinorVersion.xsd (e.g. fpml-main-5-12.xsd), for better readability the version number is omitted from the schema names below.

Confirmation Schemas:

confirmation/
* example-extension.xsd - File containing an example of an extension from the 5.x confirmation view schemas.
* fpml-asset.xsd - Underlyer definitions plus some types used by them (e.g. ones relating to commissions or dividend payouts).
* fpml-bond-option.xsd - Bond and Convertible Bond Options Product Definitions.
* fpml-business-events.xsd - Content of the Business events components
* fpml-cd.xsd - Credit derivative product definitions.
* fpml-clearing-processes.xsd - Clearing processes messages.
* fpml-com.xsd - Commodity product definitions.
* fpml-confirmation-processes.xsd - Confirmation process messages.
* fpml-correlation-swap.xsd - Correlation Swap Product Definitions.
* fpml-credit-event-notification.xsd - A message defining the ISDA defined Credit Event Notice. ISDA defines it as an irrevocable notice from a Notifying Party to the other party that describes a Credit Event that occurred. A Credit Event Notice must contain detail of the facts relevant to the determination that a Credit Event has occurred.
* fpml-dividend-swaps.xsd - Dividend Swap Product Definitions.
* fpml-doc.xsd - Trade and contract definitions and definitions relating to validation.
* fpml-enum.xsd - Shared enumeration definitions. These definitions list the values that enumerated types may take.
* fpml-eqd.xsd - Equity Option and Equity Forward Product Definitions.
* fpml-eq-shared.xsd - Definitions shared by types with Equity Underlyers.
* fpml-fx.xsd - Foreign Exchange Product Definitions.
* fpml-fx-accruals.xsd - Foreign Exchange Accruals Family Products Definitions.
* fpml-fx-targets.xsd - Foreign Exchange Targets Family Products Definitions.
* fpml-generic - Used in Transparency reporting to define a product that represents an OTC derivative transaction whose economics are not fully described using an FpML schema. In other views, generic products are present for convenience to support internal messaging and workflows that are cross-product. Generic products are not full trade representations as such they are not intended to be used for confirming trades.
* fpml-ird.xsd - Interest rate derivative product definitions.
* fpml-loan.xsd - Commercial Loans product definitions.
* fpml-main.xsd - Root definitions.
* fpml-mktenv.xsd - Definitions of market environment data structures such as yield curves, volatility matrices, and the like.
* fpml-msg.xsd - High level definitions related to messaging.
* fpml-option-shared.xsd - Shared option definitions used for defining the common features of options.
* fpml-repo.xsd - Repo definitions.
* fpml-return-swaps.xsd - Return Swaps Product Definitions.
* fpml-riskdef.xsd - Definitions of valuation and sensitivity results. They include detailed definitions of sensitivity calculations and are intended to be used by sophisticated users.
* fpml-shared.xsd - Shared definitions used widely throughout the specification. These include items such as base types, shared financial structures, etc.
* fpml-standard - Used in Transparency reporting to define a product that represents a standardized OTC derivative transaction whose economics do not need to be fully described using an FpML schema because they are implied by the product ID. In other views, standard products are present for convenience to support internal messaging and workflows that are cross-product. Standard products are not full trade representations as such they are not intended to be used for confirming trades.
* fpml-valuation.xsd - Valuation result sets and related definitions.
* fpml-variance-swap.xsd - Variance Swap Product Definitions.
* fpml-volatility-swap.xsd - Volatility Swap Product Definitions.
* xmldsig-core-schema.xsd - W3C Digital Signature Schema
  

Plus, the Confirmation view directory contains subdirectories for each group of FpML examples, namely:
	
  confirmation/business-processes/
  * allocation
  * clearing
  * collateral
  * confirmation
  * consent
  * execution-advice
  * execution-notification
  * option-events
  * option-exercise-expiry
  * packages
  * service-notification
  * trade-change-advice
  * trade-info-update

  confirmation/products/
  * bond-options
  * commodity-derivatives
  * correlation-swaps
  * credit-derivatives
  * dividend-swaps
  * equit-forwards
  * equity-options
  * equity-swaps
  * fx-derivatives
  * inflation-swaps
  * interest-rate-derivatives
  * loan
  * repo
  * securities
  * variance-swaps	 
  * volatility-swaps

  confirmation/validation/
  * invalid-testcases
