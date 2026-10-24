// A real, stopped-on-request JVM for the updater's process-safety integration test.
public final class GuardSleep {
    public static void main(String[] args) throws Exception {
        Thread.sleep(60000);
    }
}
