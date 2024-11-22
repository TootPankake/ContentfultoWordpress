<?php
/*
Plugin Name: Brimming - Template Placeholder Replacer  
Description: Runs once when the plugin is activated
Version: 1.1
Author: Emre Gumus
*/

function create_or_update_elementor_page_from_template() {
    // Store messages for admin output
    $messages = [];

    // Query WordPress to get the specified template
    $query = new WP_Query([
        'post_type' => 'elementor_library',
        'name'      => 'activity-template-4', // Replace with your specific template slug
        'posts_per_page' => 1
    ]);

    // Retrieve the template post if it exists
    $template = $query->found_posts ? $query->posts[0] : false;

    if ($template) {
        $messages[] = "Template found: {$template->post_title} (ID: {$template->ID})";

        // Retrieve and unserialize the Elementor data
        $elementor_data = get_post_meta($template->ID, '_elementor_data', true);
        $data = json_decode($elementor_data, true);

        if ($data) {
            // Query for pages created in the last hour
            $existing_pages = get_posts([
                'post_type'   => 'page',
                'post_status' => 'publish',
                'numberposts' => -1, // Retrieve all matching pages
                'date_query'  => [
                    [
                        'after' => '3 hour ago', // Limit to pages created in the last hour
                        'inclusive' => true, // Include the boundary time
                    ],
                ],
            ]);

            if (!empty($existing_pages)) {
foreach ($existing_pages as $existing_page) {
    $page_id = $existing_page->ID;

    // Get child pages for the current page
    $child_pages = get_posts([
        'post_type'   => 'page',
        'post_status' => 'publish',
        'post_parent' => $page_id, // Fetch child pages of the current page
        'numberposts' => -1,       // Retrieve all matching child pages
        'fields'      => 'ids',   // Only fetch IDs
    ]);

    // Prepare replacement data
    $custom_content = [
        '[TITLE]'   => $existing_page->post_title,
		'[TITLE2]'   => $existing_page->post_title,
        '[CONTENT]' => $existing_page->post_content,
        '[SLUG]'    => $existing_page->post_name,
    ];

    // Recursive function to replace placeholders and update `query_manual_page`
    $replace_placeholders = function ($array) use ($custom_content, $child_pages, &$replace_placeholders) {
        foreach ($array as $key => $value) {
            if (is_array($value)) {
                $array[$key] = $replace_placeholders($value);
            } elseif (is_string($value)) {
                $array[$key] = str_replace(array_keys($custom_content), array_values($custom_content), $value);
            }

            // If `query_manual_page` key is found, replace its value with child page IDs
            if ($key === 'query_manual_page') {
                $array[$key] = $child_pages; // Replace with child page IDs
            }
        }
        return $array;
    };

    // Replace placeholders in the Elementor data array
    $modified_data = $replace_placeholders($data);

    // Serialize the modified data back to JSON
    $template_content = wp_slash(json_encode($modified_data));

    // Log the updated data (for debugging)
    error_log(json_encode($modified_data));

    // Update the existing page with the modified Elementor data
    wp_update_post([
        'ID' => $page_id,
    ]);

    // Update Elementor metadata
    update_post_meta($page_id, '_elementor_data', $template_content);
    update_post_meta($page_id, '_elementor_edit_mode', 'builder');
    update_post_meta($page_id, '_elementor_template_type', 'wp-page');
    update_post_meta($page_id, '_elementor_version', ELEMENTOR_VERSION);
    update_post_meta($page_id, '_elementor_css', '');

    $messages[] = "Updated page ID: $page_id with title: {$existing_page->post_title} and child pages.";
}
            } else {
                $messages[] = "No pages found created in the last hour.";
            }
        } else {
            $messages[] = "Failed to retrieve or parse the Elementor template data.";
        }
    } else {
        $messages[] = "Template not found. Make sure the slug 'activity-template-4' is correct.";
    }

    // Store messages for display in admin notices
    set_transient('elementor_page_creation_messages', $messages, 30);
}

// Display admin notices with messages
function display_admin_notices() {
    $messages = get_transient('elementor_page_creation_messages');
    if ($messages) {
        echo '<div class="notice notice-success is-dismissible">';
        foreach ($messages as $message) {
            echo "<p>$message</p>";
        }
        echo '</div>';
        delete_transient('elementor_page_creation_messages');
    }
}
add_action('admin_notices', 'display_admin_notices');

// Create or update page on plugin activation (for testing purposes)
function create_page_on_activation() {
    create_or_update_elementor_page_from_template();
}
register_activation_hook(__FILE__, 'create_page_on_activation');


